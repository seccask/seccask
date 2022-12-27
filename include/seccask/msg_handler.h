#pragma once

#include <boost/asio.hpp>
#include <boost/asio/spawn.hpp>
#include <boost/asio/ssl.hpp>
#include <stdexcept>

#include "seccask/message.h"
#include "seccask/util.h"

namespace seccask {
class Coordinator;

class MessageHandler : public std::enable_shared_from_this<MessageHandler> {
 public:
  inline static constexpr const char* kClassName = "MessageHandler";

  enum class Mode {
    kPlaintext,
    kTLS,
    kRATLS,
  };

  MessageHandler(boost::asio::io_context& io,
                 boost::asio::ip::tcp::socket&& socket)
      : socket_(std::move(socket)),
        network_strand_(io),
        mode_(Mode::kPlaintext),
        ssl_context_(boost::asio::ssl::context::tlsv12_client) {
    read_buf_ = std::make_shared<boost::asio::streambuf>();
    util::log::Debug(kClassName,
                     "Message handler initialized with plain text mode");
  }
  MessageHandler(boost::asio::io_context& io, bool is_server = false,
                 bool is_ra_enabled = false)
      : network_strand_(io),
        socket_(io),
        mode_(is_ra_enabled ? Mode::kRATLS : Mode::kTLS),
        read_buf_(std::make_shared<boost::asio::streambuf>()),
        ssl_context_(is_server ? boost::asio::ssl::context::tlsv12_server
                               : boost::asio::ssl::context::tlsv12_client) {
    DebugShowMode();
  }
  MessageHandler(boost::asio::io_context& io,
                 boost::asio::ip::tcp::socket&& socket, bool is_server = false,
                 bool is_ra_enabled = false)
      : network_strand_(io),
        socket_(std::move(socket)),
        mode_(is_ra_enabled ? Mode::kRATLS : Mode::kTLS),
        read_buf_(std::make_shared<boost::asio::streambuf>()),
        ssl_context_(is_server ? boost::asio::ssl::context::tlsv12_server
                               : boost::asio::ssl::context::tlsv12_client) {
    DebugShowMode();
  }
  virtual ~MessageHandler();

  inline void RegisterRecvCallback(
      std::function<void(std::shared_ptr<MessageHandler>, Message)> callback) {
    callback_ = callback;
  }
  inline void RegisterConnectedCallback(
      std::function<void(std::shared_ptr<MessageHandler>)> callback) {
    connected_callback_ = callback;
  }

  void Connect(const boost::asio::ip::tcp::resolver::results_type& endpoints);

  void ServerMode(std::shared_ptr<seccask::Coordinator> coord);
  void ListenOnSocket();

  void Send(Message&& msg);
  void Send(Message&& msg, const boost::asio::yield_context& yield);
  void Spawn(std::function<void(boost::asio::yield_context)> func);
  void Close();

  inline std::string remote_addr() const {
    switch (mode_) {
      case Mode::kPlaintext:
        return ssl_socket_->lowest_layer()
            .remote_endpoint()
            .address()
            .to_string();
      case Mode::kTLS:
        return socket_.remote_endpoint().address().to_string();
      default:
        util::log::Error(kClassName, "At line {}: {}", __LINE__,
                         "Invalid mode");
    }
    return "";
  }
  inline unsigned short remote_port() const {
    switch (mode_) {
      case Mode::kPlaintext:
        return ssl_socket_->lowest_layer().remote_endpoint().port();
      case Mode::kTLS:
        return socket_.remote_endpoint().port();
      default:
        util::log::Error(kClassName, "At line {}: {}", __LINE__,
                         "Invalid mode");
    }
    return 0;
  }

 private:
  inline void DebugShowMode() {
    switch (mode_) {
      case Mode::kPlaintext:
        util::log::Debug(kClassName, "Mode: Plaintext");
        break;
      case Mode::kTLS:
        util::log::Debug(kClassName, "Mode: TLS");
        break;
      case Mode::kRATLS:
        util::log::Debug(kClassName, "Mode: RA-TLS");
        break;
      default:
        util::log::Error(kClassName, "At line {}: {}", __LINE__,
                         "Invalid mode");
    }
  }

  void DoWrite(const boost::asio::yield_context& yield);
  void DoWrite();
  void DoRead();
  void DoRead(const boost::asio::yield_context& yield);

  const Mode mode_;
  boost::asio::ip::tcp::socket socket_;
  boost::asio::ssl::context ssl_context_;
  std::shared_ptr<boost::asio::ssl::stream<boost::asio::ip::tcp::socket>>
      ssl_socket_;
  std::shared_ptr<seccask::Coordinator> coord_;
  boost::asio::io_context::strand network_strand_;
  uint32_t read_len_;
  uint32_t write_len_;
  std::shared_ptr<boost::asio::streambuf> read_buf_;
  std::deque<Message> write_msgs_;
  std::function<void(std::shared_ptr<MessageHandler>, Message)> callback_;
  std::function<void(std::shared_ptr<MessageHandler>)> connected_callback_;
};
}  // namespace seccask

template <>
struct fmt::formatter<seccask::MessageHandler> {
  template <typename ParseContext>
  constexpr auto parse(ParseContext& ctx) {
    return ctx.begin();
  }
  template <typename FormatCtx>
  auto format(const seccask::MessageHandler& a, FormatCtx& ctx) const
      -> decltype(ctx.out()) {
    return fmt::format_to(ctx.out(), "<Wkr - {}:{}>", a.remote_addr(),
                          a.remote_port());
  }
};

template <>
struct fmt::formatter<std::shared_ptr<seccask::MessageHandler>> {
  template <typename ParseContext>
  constexpr auto parse(ParseContext& ctx) {
    return ctx.begin();
  }

  template <typename FormatCtx>
  auto format(const std::shared_ptr<seccask::MessageHandler>& a,
              FormatCtx& ctx) const -> decltype(ctx.out()) {
    return fmt::format_to(ctx.out(), "<Wkr - {}:{}>", a->remote_addr(),
                          a->remote_port());
  }
};
