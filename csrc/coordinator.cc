#include "seccask/coordinator.h"

#include <fmt/format.h>
#include <pybind11/embed.h>
#include <pybind11/eval.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <boost/thread.hpp>
#include <mutex>

#include "seccask/util.h"

namespace py = pybind11;
using tcp = boost::asio::ip::tcp;
using namespace pybind11::literals;

std::mutex g_lifecycle_mutex;

double last_component_io_time;

PYBIND11_EMBEDDED_MODULE(cpp_coordinator, m) {
  m.def(
      "on_new_pipeline",
      [](std::vector<std::string> pipeline, std::vector<std::string> ids) {
        g_coordinator_ptr->OnNewPipeline(std::move(pipeline), std::move(ids));
      },
      py::arg("info").none(false), py::arg("ids").none(false));
  m.def(
      "on_new_component",
      [](std::vector<std::string> info) {
        g_coordinator_ptr->OnNewComponent(std::move(info));
        return last_component_io_time;
      },
      py::arg("info").none(false));
  m.def(
      "on_cache_full",
      [](std::string worker_id) { g_coordinator_ptr->OnCacheFull(worker_id); },
      py::arg("id").none(false));
  m.def("get_component_key",
        []() { return g_coordinator_ptr->component_key(); });
}

namespace seccask {
void Coordinator::Start() {
  util::log::Warn(kClassName, "Starting at 0.0.0.0:{}", port_);

  acceptor_ =
      std::make_shared<tcp::acceptor>(io_, tcp::endpoint(tcp::v4(), port_));

  {
    py::gil_scoped_acquire guard{};

    py::object Scheduler = py::module_::import("scheduler").attr("Scheduler");
    py_scheduler_ = std::make_shared<py::object>(Scheduler());
    py::object TaskMonitor =
        py::module_::import("daemon.coordinator").attr("TaskMonitor");
    py_task_monitor_ = std::make_shared<py::object>(TaskMonitor());
  }

  DoAccept();
}

void Coordinator::DoAccept() {
  acceptor_->async_accept(
      [this](boost::system::error_code ec, tcp::socket socket) {
        if (ec) {
          util::log::Error(kClassName, std::strerror(ec.value()));
          return;
        }

        auto worker = std::make_shared<seccask::MessageHandler>(
            io_, std::move(socket), true,
            mode_ == MessageHandler::Mode::kRATLS ? true : false);

        worker->RegisterRecvCallback(
            [this](std::shared_ptr<MessageHandler> w, Message msg) {
              DoActionFromMsg(w, std::move(msg));
            });
        worker->ServerMode(shared_from_this());
        worker->ListenOnSocket();
        new_workers_.emplace_back(std::move(worker));

        DoAccept();
      });
}

void Coordinator::OnWorkerGotID(std::shared_ptr<MessageHandler> worker,
                                std::string id) {
  auto it = std::remove_if(new_workers_.begin(), new_workers_.end(),
                           [&](std::shared_ptr<MessageHandler> w) {
                             return worker.get() == w.get();
                           });
  workers_[id] = std::move(*it);
  new_workers_.erase(it);
  util::log::Debug(kClassName, "New workers list: {}",
                   fmt::join(new_workers_, ", "));
}

void Coordinator::DoActionFromMsg(std::shared_ptr<MessageHandler> worker,
                                  Message msg) {
  util::log::Debug(kClassName, "Message: {}", msg.Repr());
  auto& id = msg.sender_id();
  auto& cmd = msg.cmd();

  if (cmd == "ping") {
    workers_[id]->Send(
        std::move(Message::MakeWithoutArgs("Coordinator", "pong")));

  } else if (cmd == "ready") {
    {
      py::gil_scoped_acquire guard{};

      py::object WorkerConnectionInfo =
          py::module_::import("workerconn").attr("WorkerConnectionInfo");
      py::object wc = WorkerConnectionInfo("id"_a = id);
      py_scheduler_->attr("add_new_worker")(wc);
    }
    OnWorkerGotID(worker, id);
    workers_[id]->Send(
        std::move(Message::MakeWithoutArgs("Coordinator", "request_manifest")));

  } else if (cmd == "response_manifest") {
    {
      py::gil_scoped_acquire guard{};

      py::object wc = py_scheduler_->attr("get_worker")(id);
      if (wc.is(py::none())) {
        util::log::Error(kClassName, "No worker with ID {}", id);
        return;
      }

      auto new_worker = wc.attr("on_msg")(msg.ToPython()).cast<bool>();
      if (new_worker) {
        py_scheduler_->attr("on_worker_ready")(
            wc, py::cpp_function([this, id](py::object component) {
              py::exec(
                  "print(f'[Coordinator] TIME OF WORKER FOUND (NEW WORKER): "
                  "{time.time()}')");

              auto command =
                  component.attr("command").cast<std::vector<std::string>>();
              util::log::Debug(kClassName,
                               "Sending component execution task to {}: {}", id,
                               fmt::join(command, ", "));
              auto msg = Message::Make("Coordinator", "execute", command);
              workers_[id]->Send(std::move(msg));
            }));
      }
    }

  } else if (cmd == "done") {
    util::log::Info(kClassName, "Component done: {}. Time spent on I/O: {}",
                    msg.args()[0], msg.args()[1]);

    last_component_io_time = std::stod(msg.args()[1]);

    {
      py::gil_scoped_acquire guard{};

      py::object wc = py_scheduler_->attr("get_worker")(id);
      if (wc.is(py::none())) {
        util::log::Error(kClassName, "No worker with ID {}", id);
        return;
      }

      py_scheduler_->attr("cache_worker")(wc);
    }
    util::log::Debug(kClassName,
                     "Worker cached: {}. Unlocking g_lifecycle_mutex...", id);
    g_lifecycle_mutex.unlock();  // This will unblock the trial manager

  } else if (cmd == "bye") {
    util::log::Info(kClassName,
                    "Worker {} disconnected. Removing from cached list", id);
    workers_[id] = nullptr;

  } else {
    util::log::Error(kClassName, "Unknown command: {}", msg.cmd());
  }
}

void Coordinator::OnCacheFull(std::string worker_id) {
  util::log::Debug(kClassName, "Worker to reclaim: {}", worker_id);
  workers_[worker_id]->Send(
      std::move(Message::MakeWithoutArgs("Coordinator", "exit")));
}

void Coordinator::OnNewLifecycle(std::string manifest_name) {
  boost::thread([this, manifest_name]() {
    AcquireGIL();

    py::object PyOnNewLifecycle =
        py::module_::import("daemon.coordinator").attr("on_new_lifecycle");

    PyOnNewLifecycle(manifest_name);
  }).detach();
}
void Coordinator::OnNewPipeline(std::vector<std::string> pipeline,
                                std::vector<std::string> ids) {
  util::log::Debug(kClassName, "Received new pipeline execution task: {}",
                   fmt::join(pipeline, ", "));

  {
    py::gil_scoped_acquire guard{};

    std::vector<py::object> components;

    py::object Component = py::module_::import("pipeline").attr("Component");

    for (int i = 0; i < pipeline.size(); i++) {
      auto c = Component("name"_a = pipeline[i], "id"_a = ids[i]);
      py_task_monitor_->attr("add_pending_components")(
          std::map<std::string, py::object>{{ids[i], c}});
    }
  }
}
void Coordinator::OnNewComponent(std::vector<std::string> info) {
  ReleaseGIL();
  boost::promise<bool> promise;
  boost::asio::post(lifecycle_strand_, [this, info, &promise]() {
    {
      py::gil_scoped_acquire guard{};
      std::string id = info[0];
      std::string working_directory = info[1];

      py::dict pc = py_task_monitor_->attr("pending_components");
      py::object component = pc[id.c_str()];
      component.attr("path") = working_directory;
      component.attr("command") = info;

      py_scheduler_->attr("get_compatible_worker_sync")(
          component, py::cpp_function([this, info](std::string worker_id) {
            py::exec(
                "print(f'[Coordinator] TIME OF WORKER FOUND (EXISTING WORKER): "
                "{time.time()}')");

            util::log::Debug(kClassName,
                             "Sending component execution task to {}: {}",
                             worker_id, fmt::join(info, ", "));
            auto msg = Message::Make("Coordinator", "execute",
                                     std::vector<std::string>(info));
            workers_[worker_id]->Send(std::move(msg));
          }));
    }
    util::log::Debug(kClassName, "Locking g_lifecycle_mutex...");
    g_lifecycle_mutex.lock();
    util::log::Debug(kClassName, "Releasing promise...");
    promise.set_value(true);
  });

  util::log::Debug(kClassName, "Waiting for promise to release...");
  promise.get_future().get();

  util::log::Debug(kClassName, "Locking g_lifecycle_mutex...");
  // This will block the current thread (the trail manager)
  g_lifecycle_mutex.lock();

  // Now the component is done
  g_lifecycle_mutex.unlock();
  util::log::Debug(kClassName, "Component {} is done. Acquiring GIL...",
                   info[0]);
  AcquireGIL();
  util::log::Debug(kClassName, "GIL acquired. Resuming trial manager...");
}

void Coordinator::AcquireGIL() {
  if (lifecycle_thread_state_) {
    PyEval_RestoreThread(lifecycle_thread_state_);
    lifecycle_thread_state_ = nullptr;
  } else {
    // The first run. Just acquire the GIL
    gil_ = PyGILState_Ensure();
  }
}
void Coordinator::ReleaseGIL() {
  lifecycle_thread_state_ = PyEval_SaveThread();
}

}  // namespace seccask
