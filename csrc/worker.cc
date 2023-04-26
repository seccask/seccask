#include "seccask/worker.h"

#include <fmt/format.h>
#include <pybind11/eval.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <boost/asio/spawn.hpp>
#include <cerrno>
#include <iostream>
#include <memory>
#include <stdexcept>

#include "seccask/encfs.h"
#include "seccask/util.h"

namespace py = pybind11;
using tcp = boost::asio::ip::tcp;
using namespace pybind11::literals;

namespace seccask {

void Worker::Start() {
  handler_->RegisterRecvCallback(
      [this](std::shared_ptr<MessageHandler> /*worker*/, Message msg) {
        DoActionFromMsg(std::move(msg));
      });

  handler_->RegisterConnectedCallback(
      [this](std::shared_ptr<MessageHandler> /*worker*/) {
        handler_->Send(Message::Make(id_, "ready", {id_}));
      });

  handler_->Connect(endpoints_);
}

void Worker::DoActionFromMsg(Message msg) {
  util::log::Debug(kClassName, "Message: {}", msg.Repr());

  try {
    if (msg.cmd() == "ping") {
      handler_->Send(std::move(Message::MakeWithoutArgs(id_, "pong")));

    } else if (msg.cmd() == "exit") {
      handler_->Send(std::move(Message::MakeWithoutArgs(id_, "bye")));
      // handler_->Close();
      // handler_ = nullptr;

    } else if (msg.cmd() == "request_manifest") {
      boost::asio::post(component_strand_, [this]() {
        std::string manifest_str;

        {
          py::gil_scoped_acquire guard{};
          py::exec("from manifest import Manifest");
          util::log::Debug(kClassName, "manifest.Manifest imported");
          manifest_str =
              py::eval(
                  fmt::format(
                      R"end(Manifest.capture_current_env(appendix={{"worker_id": "{}"}}).json())end",
                      id_))
                  .cast<std::string>();
        }

        util::log::Debug(kClassName, "Manifest for current env: {}",
                         manifest_str);
        std::vector<std::string> manifest = {manifest_str};
        handler_->Send(
            std::move(Message::Make(id_, "response_manifest", manifest)));
      });

    } else if (msg.cmd() == "execute") {
      const std::vector<std::string> &args = msg.args();
      std::string component_id = args[0];
      std::string working_directory = args[1];
      std::string component_key = args[2];
      std::vector<std::string> cmds;
      cmds.assign(args.begin() + 3, args.end());

      if (component_key == "NULL") {
        util::log::Warn(
            kClassName,
            "Component key is empty. Do not do component encryption");
      } else {
        encfs::InitWithKey(component_key);
      }

      util::log::Debug(kClassName, "Execute component {} at {} with args [{}]",
                       component_id, working_directory, fmt::join(cmds, " "));
      boost::asio::post(component_strand_, [this, component_id,
                                            working_directory, cmds]() {
        std::string manifest_str;
        std::string finished_component_id;

        util::log::Debug(
            kClassName, "In thread - Execute component {} at {} with args [{}]",
            component_id, working_directory, fmt::join(cmds, " "));

        double io_time = 0.0;

        {
          py::gil_scoped_acquire guard{};
          py::object execute_component =
              py::module_::import("daemon.worker").attr("execute_component");

          g_sc_time_spent_on_io = 0.0;

          finished_component_id =
              execute_component("component_id"_a = component_id,
                                "working_directory"_a = working_directory,
                                "cmds"_a = cmds)
                  .cast<std::string>();

          io_time = g_sc_time_spent_on_io;

          manifest_str =
              py::eval(
                  fmt::format(
                      R"end(Manifest.capture_current_env(appendix={{"worker_id": "{}"}}).json())end",
                      id_))
                  .cast<std::string>();
        }

        util::log::Debug(kClassName, "Component {} finished with manifest: {}",
                         finished_component_id, manifest_str);

        handler_->Spawn([this, finished_component_id, manifest_str,
                         io_time](boost::asio::yield_context yield) {
          handler_->Send(std::move(Message::Make(id_, "response_manifest",
                                                 {manifest_str})),
                         yield);
          handler_->Send(std::move(Message::Make(id_, "done",
                                                 {finished_component_id,
                                                  fmt::format("{}", io_time)})),
                         yield);
        });
      });
    } else {
      util::log::Error(kClassName, "Unknown command: {}", msg.cmd());
    }
  } catch (std::exception &e) {
    util::log::Error(kClassName, e.what());
  }
}
}  // namespace seccask