#include "seccask/msg_handler.h"

#include "seccask/config.h"
#include "seccask/ratls.h"
#include "seccask/util.h"

namespace seccask {
void MessageHandler::Connect(
    const boost::asio::ip::tcp::resolver::results_type& endpoints) {
  if (mode_ == Mode::kPlaintext) {
  } else if (mode_ == Mode::kTLS) {
    ssl_socket_ = std::make_shared<
        boost::asio::ssl::stream<boost::asio::ip::tcp::socket>>(
        std::move(socket_), ssl_context_);
    ssl_socket_->set_verify_mode(boost::asio::ssl::verify_peer);
    ssl_socket_->set_verify_callback(
        [this](bool preverified, boost::asio::ssl::verify_context& ctx) {
          return RATLS::Get().PrintCertOnly(preverified, ctx);
        });

  } else if (mode_ == Mode::kRATLS) {
    RATLS::Get().InitVerification();
    ssl_socket_ = std::make_shared<
        boost::asio::ssl::stream<boost::asio::ip::tcp::socket>>(
        std::move(socket_), ssl_context_);
    ssl_socket_->set_verify_mode(boost::asio::ssl::verify_peer);
    ssl_socket_->set_verify_callback(
        [this](bool preverified, boost::asio::ssl::verify_context& ctx) {
          return RATLS::Get().Verify(preverified, ctx);
        });

  } else {
    util::log::Error(kClassName, "At line {}: {}", __LINE__, "Invalid mode");
    return;
  }

  boost::asio::spawn(network_strand_, [this, &endpoints](
                                          boost::asio::yield_context yield) {
    boost::system::error_code ec;

    util::log::Debug(kClassName,
                     fmt::format("At line {}: Connecting", __LINE__));

    mode_ == Mode::kPlaintext
        ? boost::asio::async_connect(socket_, endpoints, yield[ec])
        : boost::asio::async_connect(ssl_socket_->lowest_layer(), endpoints,
                                     yield[ec]);
    if (ec) {
      util::log::Error(kClassName,
                       fmt::format("At line {}: Connection failed with {}",
                                   __LINE__, util::OpenSSLError2String(ec)));
      return;
    }

    util::log::Debug(kClassName,
                     fmt::format("At line {}: Connected", __LINE__));

    if (mode_ != Mode::kPlaintext) {
      util::log::Debug(kClassName,
                       fmt::format("At line {}: Handshaking...", __LINE__));

      timespec time1, time2;
      clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &time1);

      ssl_socket_->async_handshake(boost::asio::ssl::stream_base::client,
                                   yield[ec]);

      clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &time2);
      timespec duration = util::TimeDiff(time1, time2);
      util::log::Debug(kClassName, "Time diff for RA-TLS handshake: {}:{}",
                       duration.tv_sec, duration.tv_nsec);

      if (ec) {
        util::log::Error(kClassName,
                         fmt::format("At line {}: Handshake failed with {}",
                                     __LINE__, util::OpenSSLError2String(ec)));
        return;
      }
      util::log::Debug(kClassName,
                       fmt::format("At line {}: Handshaked", __LINE__));
    }

    if (connected_callback_) {
      connected_callback_(shared_from_this());
    }

    DoRead();
  });
}

void MessageHandler::ServerMode(std::shared_ptr<seccask::Coordinator> coord) {
  coord_ = coord;

  if (mode_ == Mode::kTLS) {
    ssl_context_.use_certificate_chain_file(
        "/home/mlcask/sgx/seccask2/build/cert.pem");
    ssl_context_.use_private_key_file("/home/mlcask/sgx/seccask2/build/key.pem",
                                      boost::asio::ssl::context::pem);

  } else if (mode_ == Mode::kRATLS) {
    RATLS::Get().InitQuoteGeneration();
    RATLS::SetupSSLContext(ssl_context_);
  }

  if (mode_ != Mode::kPlaintext) {
    ssl_socket_ = std::make_shared<
        boost::asio::ssl::stream<boost::asio::ip::tcp::socket>>(
        std::move(socket_), ssl_context_);
  }

  // ssl_socket_->set_verify_mode(boost::asio::ssl::verify_peer);
  // ssl_socket_->set_verify_callback(
  //     [this](bool preverified, boost::asio::ssl::verify_context& ctx) {
  //       return DoVerifyServer(preverified, ctx);
  //     });
}

void MessageHandler::ListenOnSocket() {
  switch (mode_) {
    case Mode::kPlaintext:
      break;
    case Mode::kTLS:
      ssl_socket_->async_handshake(
          boost::asio::ssl::stream_base::server,
          [this](boost::system::error_code ec) {
            if (ec) {
              util::log::Error(kClassName,
                               fmt::format("At line {}: {}", __LINE__,
                                           util::OpenSSLError2String(ec)));
              return;
            }
            DoRead();
          });
      break;
    case Mode::kRATLS:
      ssl_socket_->async_handshake(
          boost::asio::ssl::stream_base::server,
          [this](boost::system::error_code ec) {
            if (ec) {
              util::log::Error(kClassName,
                               fmt::format("At line {}: {}", __LINE__,
                                           util::OpenSSLError2String(ec)));
              return;
            }
            DoRead();
          });
      break;
    default:
      util::log::Error(kClassName, "At line {}: {}", __LINE__, "Invalid mode");
  }
}

/**
 * @brief Perform read operation from socket.
 *
 */
void MessageHandler::DoRead() {
  boost::asio::spawn(network_strand_, [this](boost::asio::yield_context yield) {
    DoRead(yield);
  });
}

/**
 * @brief Perform read operation from socket synchronously.
 *
 * @param yield Yield context for `Boost.Asio`.
 *
 * Note that passing `yield` into any async operations (e.g., `async_read`,
 * `async_write`) will block them until the operation is done.
 */
void MessageHandler::DoRead(const boost::asio::yield_context& yield) {
  boost::system::error_code ec;
  // The next line will block until async I/O is done. Same below
  mode_ == Mode::kPlaintext
      ? boost::asio::async_read(socket_, boost::asio::buffer(&read_len_, 4),
                                boost::asio::transfer_exactly(4), yield[ec])
      : boost::asio::async_read(*ssl_socket_,
                                boost::asio::buffer(&read_len_, 4),
                                boost::asio::transfer_exactly(4), yield[ec]);

  if (ec) {
    util::log::Error(kClassName, fmt::format("At line {}: {}", __LINE__,
                                             std::strerror(ec.value())));
    return;
  }
  read_len_ = util::SwapEndian(read_len_);

  mode_ == Mode::kPlaintext
      ? boost::asio::async_read(socket_, *read_buf_,
                                boost::asio::transfer_exactly(read_len_),
                                yield[ec])
      : boost::asio::async_read(*ssl_socket_, *read_buf_,
                                boost::asio::transfer_exactly(read_len_),
                                yield[ec]);
  if (ec) {
    util::log::Error(kClassName, fmt::format("At line {}: {}", __LINE__,
                                             std::strerror(ec.value())));
    return;
  }

  std::string msg_str((std::istreambuf_iterator<char>(read_buf_.get())),
                      std::istreambuf_iterator<char>());
  read_buf_->consume(read_len_);
  util::log::Debug(kClassName, "msg_str: [{}] {}", read_len_, msg_str);

  auto try_msg = Message::MakeFromString(msg_str);
  if (!try_msg.has_value()) {
    util::log::Error(kClassName, "Message parse failed");
    return;
  }

  if (callback_) {
    util::log::Debug(kClassName, "Calling callback with message");
    callback_(shared_from_this(), std::move(try_msg.value()));
  } else {
    util::log::Warn(kClassName,
                    "Incoming message has no callback to process. Ignored");
  }

  DoRead(yield);
}

void MessageHandler::Send(Message&& msg) {
  write_msgs_.emplace_back(std::move(msg));
  DoWrite();
}

void MessageHandler::DoWrite() {
  boost::asio::spawn(network_strand_, [this](boost::asio::yield_context yield) {
    DoWrite(std::forward<boost::asio::yield_context>(yield));
  });
}

void MessageHandler::Send(Message&& msg,
                          const boost::asio::yield_context& yield) {
  write_msgs_.emplace_back(std::move(msg));
  DoWrite(yield);
}

void MessageHandler::DoWrite(const boost::asio::yield_context& yield) {
  boost::system::error_code ec;
  auto msg = write_msgs_.front().ToString();
  write_len_ = msg.length();
  write_len_ = util::SwapEndian(write_len_);
  spdlog::debug("write_len_ in big endian: {}", write_len_);

  mode_ == Mode::kPlaintext
      ? boost::asio::async_write(socket_, boost::asio::buffer(&write_len_, 4),
                                 yield[ec])
      : boost::asio::async_write(
            *ssl_socket_, boost::asio::buffer(&write_len_, 4), yield[ec]);
  if (ec) {
    util::log::Error(kClassName, fmt::format("At line {}: {}", __LINE__,
                                             std::strerror(ec.value())));
    return;
  }

  mode_ == Mode::kPlaintext
      ? boost::asio::async_write(
            socket_, boost::asio::buffer(msg, msg.length()), yield[ec])
      : boost::asio::async_write(
            *ssl_socket_, boost::asio::buffer(msg, msg.length()), yield[ec]);
  if (ec) {
    util::log::Error(kClassName, fmt::format("At line {}: {}", __LINE__,
                                             std::strerror(ec.value())));
    return;
  }

  util::log::Info(kClassName, "Message sent: [{}] {}", write_len_, msg);

  if (write_msgs_.front().cmd() == "bye") {
    socket_.close();
    return;
  }

  write_msgs_.pop_front();
  if (!write_msgs_.empty()) {
    DoWrite();
  }
}

void MessageHandler::Spawn(
    std::function<void(boost::asio::yield_context)> func) {
  boost::asio::spawn(network_strand_, func);
}

MessageHandler::~MessageHandler() { read_buf_ = nullptr; }

}  // namespace seccask