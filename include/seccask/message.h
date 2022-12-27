#pragma once

#include <fmt/format.h>
#include <pybind11/pybind11.h>

#include <iostream>
#include <optional>
#include <regex>
#include <string>
#include <vector>

#include "seccask/util.h"

namespace py = pybind11;

namespace seccask {

class Message {
 public:
  inline static constexpr const char* kDelimiter = "%";
  inline static constexpr const char* kClassName = "Message";
  inline static constexpr const char* kRegexPattern =
      R"end(^(.+)\r\n(.+)\r\n(.*)$)end";

  Message(std::string sender_id, std::string cmd, std::vector<std::string> args)
      : sender_id_(sender_id), cmd_(cmd), args_(args) {}
  Message(const Message& rhs) =
      delete; /**< Copy constructor disabled. Consider either moving the
                 existing message or recreating by factory methods */
  Message(Message&& rhs) noexcept
      : sender_id_(std::move(rhs.sender_id_)),
        cmd_(std::move(rhs.cmd_)),
        args_(std::move(rhs.args_)) {}

  static Message Make(std::string sender_id, std::string cmd,
                      std::vector<std::string> args);
  static Message MakeWithoutArgs(std::string sender_id, std::string cmd);
  static std::optional<Message> MakeFromString(const std::string& value);

  const std::string& sender_id() const { return sender_id_; }
  const std::string& cmd() const { return cmd_; }
  const std::vector<std::string>& args() const { return args_; }

  inline std::string ToString() const {
    return fmt::format("{}\r\n{}\r\n{}", sender_id_, cmd_,
                       fmt::join(args_, kDelimiter));
  }

  inline std::string Repr() const {
    return fmt::format("Message {{ sender_id: {}, cmd: {}, args: [{}] }}",
                       sender_id_, cmd_, fmt::join(args_, " "));
  }

  py::object ToPython() const;

 private:
  std::string sender_id_;
  std::string cmd_;
  std::vector<std::string> args_;
};
}  // namespace seccask