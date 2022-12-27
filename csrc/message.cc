#include "seccask/message.h"

#include <pybind11/stl.h>

#include <boost/algorithm/string.hpp>
#include <boost/regex.hpp>

using namespace pybind11::literals;

namespace seccask {
Message Message::Make(std::string sender_id, std::string cmd,
                      std::vector<std::string> args) {
  auto copy_sender_id = sender_id;
  auto copy_cmd = cmd;
  auto copy_args = args;
  util::log::Debug(kClassName, "New message: {} {} [{}]", copy_sender_id,
                   copy_cmd, fmt::join(copy_args, " "));
  return Message(copy_sender_id, copy_cmd, copy_args);
}

Message Message::MakeWithoutArgs(std::string sender_id, std::string cmd) {
  return Message::Make(sender_id, cmd, std::move(std::vector<std::string>()));
}

std::optional<Message> Message::MakeFromString(const std::string& value) {
  std::string parsed_id;
  std::string parsed_cmd;
  std::vector<std::string> parsed_args;

  boost::smatch match;
  auto is_matched =
      boost::regex_search(value, match, boost::regex(kRegexPattern));
  if (!is_matched) {
    return std::nullopt;
  }

  util::log::Debug(kClassName, "Has {} matches:", match.size() - 1);
  for (int i = 1; i < match.size(); i++) {
    util::log::Debug(kClassName, "{}", std::string{match[i]});
  }

  parsed_id = match[1];
  parsed_cmd = match[2];
  std::string parsed_args_str = match[3];
  if (parsed_args_str.size() == 0) {
    // No args
    util::log::Debug(kClassName, "Parsed message: {} {}", parsed_id,
                     parsed_cmd);
  } else {
    // Has args. Try to parse
    util::log::Debug(kClassName, "args_str: {}", parsed_args_str);
    boost::split(parsed_args, parsed_args_str, boost::is_any_of(kDelimiter));
    util::log::Debug(kClassName, "Parsed message: {} {} [{}]", parsed_id,
                     parsed_cmd, fmt::join(parsed_args, " "));
  }

  return Message::Make(parsed_id, parsed_cmd, parsed_args);
}

py::object Message::ToPython() const {
  py::gil_scoped_acquire guard{};
  py::object Message = py::module_::import("daemon.message").attr("Message");
  return Message("sender_id"_a = sender_id_, "cmd"_a = cmd_, "args"_a = args_);
}
}  // namespace seccask