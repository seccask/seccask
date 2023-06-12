#pragma once

#include <INIReader.h>
#include <limits.h>
#include <pwd.h>
#include <unistd.h>

#include <boost/algorithm/string/replace.hpp>
#include <boost/filesystem.hpp>

#include "seccask/util.h"

namespace seccask {
class Config : public INIReader {
 public:
  inline static constexpr const char* kClassName = "Config";
  inline static constexpr const char* kDefaultCoordinatorHost = "127.0.0.1";
  inline static constexpr unsigned short kDefaultCoordinatorPort = 50200;

  Config(Config const&) = delete;
  void operator=(Config const&) = delete;
  virtual ~Config() = default;

  inline static Config& Get() {
    auto app_home = std::getenv(kEnvVar);
    if (app_home == NULL) {
      util::log::Error(kClassName,
                       "Environmental variable APP_HOME not set. Please set it "
                       "to the root folder of SecCask");
      exit(-1);
    }

    auto conf_path = boost::filesystem::canonical(kConfigFilePath, app_home);

    static Config config(conf_path.c_str());

    if (config.ParseError() < 0) {
      util::log::Error(kClassName,
                       "Cannot parse config file: {}. Please check the syntax",
                       conf_path.c_str());
      exit(-1);
    }

    return config;
  }

  inline static std::string GetStr(const std::string& section,
                                   const std::string& name,
                                   const std::string& default_value) {
    std::string result = Get().GetString(section, name, default_value);
    boost::replace_all(result, "$HOME", std::getenv("HOME"));
    boost::replace_all(result, "$USER", Get().User());
    boost::replace_all(result, "$SCWD", std::getenv("PWD"));
    return result;
  }

  inline static int NumIOThreads() {
    return Get().GetInteger("env", "num_threads", 2);
  }
  inline static std::string CoordinatorHost() {
    return Get().GetStr("coordinator", "host", kDefaultCoordinatorHost);
  }
  inline static unsigned short CoordinatorPort() {
    return static_cast<unsigned short>(Get().GetInteger(
        "coordinator", "worker_manager_port", kDefaultCoordinatorPort));
  }
  inline static bool IsRATLSEnabled() {
    return Get().GetBoolean("ratls", "enable_ratls", false);
  }
  inline static std::string MREnclave() {
    return Get().GetStr("ratls", "mrenclave", "");
  }
  inline static std::string MRSigner() {
    return Get().GetStr("ratls", "mrsigner", "");
  }
  inline static std::string User() { return Get().user_; }

 private:
  Config(const std::string& filename)
      : INIReader(filename), user_(GetCurrentUserName()) {}

  inline static std::string GetCurrentUserName() {
    struct passwd* pw = getpwuid(geteuid());
    return pw ? pw->pw_name : std::string{};
  }

  std::string user_;
  std::string scwd_;

  inline static constexpr const char* kEnvVar = "APP_HOME";
  inline static constexpr const char* kConfigFilePath = ".conf/config.ini";
};
}  // namespace seccask