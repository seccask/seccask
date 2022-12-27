#include <INIReader.h>
#include <fmt/format.h>
#include <pybind11/embed.h>
#include <pybind11/stl.h>
#include <spdlog/spdlog.h>

#include <CLI/App.hpp>
#include <CLI/Config.hpp>
#include <CLI/Formatter.hpp>

#ifdef ENABLE_BACKWARD_CPP
#include <backward.hpp>
#endif

#include <boost/asio.hpp>
#include <boost/filesystem.hpp>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <iterator>
#include <magic_enum.hpp>
#include <sstream>
#include <vector>

#include "seccask/config.h"
#include "seccask/coordinator.h"
#include "seccask/encfs.h"
#include "seccask/ustore.h"
#include "seccask/util.h"
#include "seccask/worker.h"

using namespace seccask;
namespace py = pybind11;
using mhmode = seccask::MessageHandler::Mode;
using tcp = boost::asio::ip::tcp;

inline constexpr const char* kClassName = "main";

std::shared_ptr<seccask::Coordinator> g_coordinator_ptr;
std::shared_ptr<seccask::Ustore> g_ustore_ptr;

double g_sc_time_spent_on_io;

PYBIND11_EMBEDDED_MODULE(cpp_io_profiler, m) {
  m.def("get", []() -> double { return g_sc_time_spent_on_io; });
}

inline static void PrintLogo() {
  // clang-format off
  std::cout << R"(  _____            _____          _      ___  )" << std::endl;
  std::cout << R"( / ____|          / ____|        | |    |__ \ )" << std::endl;
  std::cout << R"(| (___   ___  ___| |     __ _ ___| | __    ) |)" << std::endl;
  std::cout << R"( \___ \ / _ \/ __| |    / _` / __| |/ /   / / )" << std::endl;
  std::cout << R"( ____) |  __/ (__| |___| (_| \__ \   <   / /_ )" << std::endl;
  std::cout << R"(|_____/ \___|\___|\_____\__,_|___/_|\_\ |____|)" << std::endl;
  std::cout << std::endl;
  // clang-format on
}

inline static void InitLogging() {
  spdlog::set_level(spdlog::level::debug);
  spdlog::set_pattern("[%H:%M:%S %z] [%^---%L---%$] [thread %t] %v");
}

inline static void DebugShowArgcArgv(int argc, const char** argv) {
  util::log::Debug(kClassName, "argc = {}", argc);
  util::log::Debug(kClassName, "argv = [{}]",
                   fmt::join(argv, argv + argc, ", "));
}

inline static void DebugShowSysPath() {
  auto sys_path =
      py::module::import("sys").attr("path").cast<std::vector<std::string>>();
  util::log::Debug(kClassName, "sys.path = [{}]", fmt::join(sys_path, ", "));
}

inline static std::string GetFileContent(std::string path) {
  std::ifstream t(path);
  std::stringstream buffer;
  buffer << t.rdbuf();
  return buffer.str();
}

int main(int argc, const char** argv) {
  char unbuffered_c[] = "PYTHONUNBUFFERED=1";
  putenv(unbuffered_c);
  setvbuf(stdout, NULL, _IOLBF, 0);

#ifdef ENABLE_BACKWARD_CPP
  backward::SignalHandling sh;
#endif

  PrintLogo();
  InitLogging();
  DebugShowArgcArgv(argc, argv);

  bool start_as_coordinator;
  std::string manifest_name;
  std::vector<std::string> args;
  std::string id;
  std::string coord_host;
  std::string key;
  unsigned short coord_port;
  mhmode mode{mhmode::kPlaintext};

  CLI::App app{"SecCask 2"};
  app.add_flag("--coordinator,-C,!--worker,!-W", start_as_coordinator,
               "Start as coordinator or worker")
      ->required();
  app.add_option("-i,--id", id, "Worker ID");
  app.add_option("-m,--manifest", manifest_name,
                 "Manifest name (without `exp_` and `.yaml`)");
  app.add_option("-H,--coord-host", coord_host,
                 "(Only for worker) Coordinator host to connect")
      ->default_val(seccask::Config::kDefaultCoordinatorHost);
  app.add_option("-P,--coord-port", coord_port,
                 "(Only for worker) Coordinator port to connect")
      ->default_val(seccask::Config::kDefaultCoordinatorPort);
  app.add_option("-k, --key", key, "Component key");

  std::map<std::string, mhmode> map{{"plain", mhmode::kPlaintext},
                                    {"tls", mhmode::kTLS},
                                    {"ratls", mhmode::kRATLS}};
  app.add_option("-M,--mode", mode, "Message handler mode")
      ->transform(CLI::CheckedTransformer(map, CLI::ignore_case));

  CLI11_PARSE(app, argc, argv);

  util::log::Info(kClassName, "Message handler mode: {}",
                  magic_enum::enum_name(mode));

  util::log::Debug(kClassName, start_as_coordinator ? "Start as coordinator"
                                                    : "Start as worker");

  auto& conf = seccask::Config::Get();

  if (start_as_coordinator) {
    // Start as coordinator
    if (manifest_name.size() == 0) {
      util::log::Error(kClassName,
                       "Should specify a manifest to start the coordinator");
      exit(-1);
    }

    if (seccask::Config::Get().GetStr("storage", "storage_engine",
                                      "filesystem") == "forkbase") {
      util::log::Info(kClassName, "Use GlassDB as storage engine");
      seccask::Ustore::InitEnvVar();
      g_ustore_ptr = std::make_shared<seccask::Ustore>();
    }

    {
      py::scoped_interpreter interp{};
      py::gil_scoped_release release{};

      boost::asio::io_context io;
      boost::asio::executor_work_guard<boost::asio::io_context::executor_type>
          work_guard(io.get_executor());

      g_coordinator_ptr = std::make_shared<seccask::Coordinator>(
          mode, io, seccask::Config::CoordinatorPort());

      if (key.size() != 0) {
        encfs::InitWithKey(key);
        g_coordinator_ptr->set_component_key(key);
      }

      g_coordinator_ptr->Start();

      std::vector<std::thread> threads;

      for (int n = 0; n < conf.NumIOThreads(); ++n) {
        threads.emplace_back([&] { io.run(); });
      }

      g_coordinator_ptr->OnNewLifecycle(manifest_name);

      for (auto& thread : threads) {
        if (thread.joinable()) {
          thread.join();
        }
      }
    }

  } else {
    // Start as worker
    if (id.size() == 0) {
      util::log::Error(kClassName, "Should specify Worker ID");
      exit(-1);
    }

    {
      py::scoped_interpreter interp{};
      py::gil_scoped_release release{};

      boost::asio::io_context io;
      boost::asio::executor_work_guard<boost::asio::io_context::executor_type>
          work_guard(io.get_executor());

      tcp::resolver resolver(io);

      auto endpoints = resolver.resolve(coord_host, std::to_string(coord_port));
      seccask::Worker w(mode, id, io, endpoints);
      w.Start();

      std::vector<std::thread> threads;

      for (int n = 0; n < conf.NumIOThreads(); ++n) {
        threads.emplace_back([&] { io.run(); });
      }

      for (auto& thread : threads) {
        if (thread.joinable()) {
          thread.join();
        }
      }
    }
  }

  spdlog::warn("Bye");

  return 0;
}