#pragma once

#include <openssl/err.h>
#include <spdlog/spdlog.h>
#include <time.h>

#include <boost/lexical_cast.hpp>
#include <boost/system/error_code.hpp>
#include <climits>
#include <cstdlib>
#include <memory>
#include <string>
#include <typeinfo>

extern "C" {
extern double g_sc_time_spent_on_io;
}

namespace seccask {
namespace util {

namespace log {
template <typename... Args>
inline void Error(std::string name, std::string format_str, Args &&...log) {
  spdlog::error(
      fmt::format("{} |> " + format_str, name, std::forward<Args>(log)...));
}
template <typename... Args>
inline void Warn(std::string name, std::string format_str, Args &&...log) {
  spdlog::warn(
      fmt::format("{} |> " + format_str, name, std::forward<Args>(log)...));
}
template <typename... Args>
inline void Info(std::string name, std::string format_str, Args &&...log) {
  spdlog::info(
      fmt::format("{} |> " + format_str, name, std::forward<Args>(log)...));
}
template <typename... Args>
inline void Debug(std::string name, std::string format_str, Args &&...log) {
  spdlog::debug(
      fmt::format("{} |> " + format_str, name, std::forward<Args>(log)...));
}
}  // namespace log

inline ssize_t ReadFile(const char *path, char *buf, size_t count) {
  FILE *f = fopen(path, "r");
  if (!f) return -errno;

  ssize_t bytes = fread(buf, 1, count, f);
  if (bytes <= 0) {
    int errsv = errno;
    fclose(f);
    return -errsv;
  }

  int close_ret = fclose(f);
  if (close_ret < 0) return -errno;

  return bytes;
}

inline std::string OpenSSLError2String(const boost::system::error_code &ec) {
  std::string err = ec.message();
  err = std::string(" (") +
        boost::lexical_cast<std::string>(ERR_GET_LIB(ec.value())) + "," +
        boost::lexical_cast<std::string>(ERR_GET_FUNC(ec.value())) + "," +
        boost::lexical_cast<std::string>(ERR_GET_REASON(ec.value())) + ") ";
  // ERR_PACK /* crypto/err/err.h */
  char buf[128];
  ::ERR_error_string_n(ec.value(), buf, sizeof(buf));
  err += buf;

  return err;
}

inline std::string OpenSSLError2String() {
  unsigned long n = ERR_get_error();
  char buf[128];
  ::ERR_error_string_n(n, buf, sizeof(buf));

  return std::string(buf);
}

template <typename T>
inline T SwapEndian(T u) {
  static_assert(CHAR_BIT == 8, "CHAR_BIT != 8");

  union {
    T u;
    unsigned char u8[sizeof(T)];
  } source, dest;

  source.u = u;

  for (size_t k = 0; k < sizeof(T); k++)
    dest.u8[k] = source.u8[sizeof(T) - k - 1];

  return dest.u;
}

inline std::vector<std::string> &split(const std::string &s, char delim,
                                       std::vector<std::string> &elems) {
  std::stringstream ss(s);
  std::string item;
  while (std::getline(ss, item, delim)) {
    elems.push_back(item);
  }
  return elems;
}

// https://stackoverflow.com/a/6749766/11144085
inline timespec TimeDiff(timespec start, timespec end) {
  timespec temp;
  if ((end.tv_nsec - start.tv_nsec) < 0) {
    temp.tv_sec = end.tv_sec - start.tv_sec - 1;
    temp.tv_nsec = 1000000000 + end.tv_nsec - start.tv_nsec;
  } else {
    temp.tv_sec = end.tv_sec - start.tv_sec;
    temp.tv_nsec = end.tv_nsec - start.tv_nsec;
  }
  return temp;
}

}  // namespace util
}  // namespace seccask
