#pragma once

#include <fmt/format.h>
#include <pybind11/pybind11.h>

#include <boost/asio.hpp>
#include <deque>
#include <memory>
#include <string>
#include <vector>

#include "seccask/message.h"
#include "seccask/msg_handler.h"

namespace seccask {
class __attribute__((visibility("hidden"))) Coordinator
    : public std::enable_shared_from_this<Coordinator> {
 public:
  inline static constexpr const char* kClassName = "Coordinator";

  // for ssl/tls mode
  Coordinator(seccask::MessageHandler::Mode mode, boost::asio::io_context& io,
              unsigned short port)
      : mode_(mode),
        io_(io),
        port_(port),
        lifecycle_strand_(io),
        lifecycle_thread_state_(nullptr),
        component_key_() {
    memset(&gil_, 0, sizeof(PyGILState_STATE));
  }

  virtual ~Coordinator() {}

  void Start();
  void OnNewLifecycle(std::string manifest_name);
  void OnNewPipeline(std::vector<std::string> pipeline,
                     std::vector<std::string> ids);
  void OnNewComponent(std::vector<std::string> info);
  void OnCacheFull(std::string worker_id);
  void OnWaitingNewWorker();
  void OnWorkerGotID(std::shared_ptr<MessageHandler> worker, std::string id);

  const std::string& component_key() const { return component_key_; }
  template <class StringType>
  void set_component_key(StringType&& name) {
    component_key_ = std::forward<StringType>(name);
  }

 private:
  void AcquireGIL();
  void ReleaseGIL();
  void DoAccept();
  void DoActionFromMsg(std::shared_ptr<MessageHandler> worker, Message msg);

  unsigned short port_;
  seccask::MessageHandler::Mode mode_;
  boost::asio::io_context& io_;
  boost::asio::io_context::strand lifecycle_strand_;
  std::map<std::string, std::shared_ptr<MessageHandler>> workers_;
  std::vector<std::shared_ptr<MessageHandler>> new_workers_;
  std::shared_ptr<boost::asio::ip::tcp::acceptor> acceptor_;
  std::shared_ptr<py::object> py_scheduler_;
  std::shared_ptr<py::object> py_task_monitor_;
  PyGILState_STATE gil_;
  PyThreadState* lifecycle_thread_state_;
  std::string component_key_;
};
}  // namespace seccask

extern std::shared_ptr<seccask::Coordinator> g_coordinator_ptr;
