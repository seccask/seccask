#pragma once

#include <fmt/format.h>

#include <boost/asio.hpp>
#include <boost/asio/ssl.hpp>
#include <deque>
#include <memory>
#include <string>
#include <vector>

#include "seccask/message.h"
#include "seccask/msg_handler.h"
#include "seccask/util.h"

namespace seccask {

class Worker {
 public:
  inline static constexpr const char* kClassName = "Worker";

  Worker(MessageHandler::Mode mode, std::string id, boost::asio::io_context& io,
         const boost::asio::ip::tcp::resolver::results_type& endpoints)
      : mode_(mode), id_(id), component_strand_(io), endpoints_(endpoints) {
    if (mode_ == MessageHandler::Mode::kPlaintext) {
      // handler_ = std::make_shared<MessageHandler>(io, false, false);
      util::log::Error(kClassName, "Not Implemented");
      exit(-1);
    } else if (mode_ == MessageHandler::Mode::kTLS) {
      handler_ = std::make_shared<MessageHandler>(io, false, false);
    } else if (mode_ == MessageHandler::Mode::kRATLS) {
      handler_ = std::make_shared<MessageHandler>(io, false, true);
    } else {
      util::log::Error(kClassName, "Unknown message handler mode");
      exit(-1);
    }
  }
  void Start();
  virtual ~Worker() {}

 private:
  void DoActionFromMsg(Message msg);

  seccask::MessageHandler::Mode mode_;
  std::string id_;
  std::shared_ptr<MessageHandler> handler_;
  boost::asio::io_context::strand component_strand_;
  const boost::asio::ip::tcp::resolver::results_type& endpoints_;
};

}  // namespace seccask