#pragma once

#include <cluster/worker_client.h>
#include <cluster/worker_client_service.h>
#include <spec/object_db.h>

#include <memory>

#include "seccask/util.h"

namespace seccask {
class Ustore {
 public:
  inline static constexpr const char* kClassName = "GlassDB";

  static void InitEnvVar();

  // Ustore() {
  Ustore() : service_() {
    service_.Run();
    wc_ = std::make_shared<ustore::WorkerClient>(service_.CreateWorkerClient());
    os_ = std::make_shared<ustore::ObjectDB>(wc_.get());
  }
  virtual ~Ustore() {}

  // std::string GetString(const std::string& key, const std::string& branch);
  // std::string GetBlob();
  // std::string PutString(const std::string& key, const std::string& branch,
  //                       const std::string& str);
  // std::string PutBlob(const std::string& key, const std::string& branch,
  //                     const std::string& file_path);

  std::string Get(const std::string& key, const std::string& branch,
                  const std::string& hversion, const std::string& output_path);
  std::string Put(const std::string& key, const std::string& branch,
                  const std::string& str, const std::string& input_path);

 private:
  inline std::string MakeFailedReturn(const std::string& action,
                                      const std::string& key,
                                      const std::string& branch,
                                      ustore::ErrorCode error_code,
                                      const std::string& error_message) {
    std::stringstream ss;
    ss << BOLD_RED(fmt::format("[FAILED: {}] ", action)) << "Key: \"" << key
       << "\", "
       << "Branch: \"" << branch << "\""
       << RED(fmt::format(" --> Error({}): {}",
                          static_cast<unsigned char>(error_code),
                          error_message));
    return ss.str();
  }
  inline std::string MakeFileNotFoundReturn(const std::string& file_path) {
    std::stringstream ss;
    ss << BOLD_RED("[FAILED: PUT] ") << file_path << "does not exist";
    return ss.str();
  }
  inline std::string MakeStringGetReturn(const std::string& key,
                                         const std::string& branch,
                                         const ustore::UType& type,
                                         const ustore::Slice& value) {
    std::stringstream ss;
    ss << BOLD_GREEN("[SUCCESS: GET] ") << "Value"
       << "<" << type << ">: \"" << value << "\"";
    return ss.str();
  }
  inline std::string MakeBlobGetReturn(const std::string& key,
                                       const std::string& branch,
                                       const ustore::UType& type,
                                       const ustore::Hash& hash) {
    std::stringstream ss;
    ss << BOLD_GREEN("[SUCCESS: GET] ") << "Value"
       << "<" << type << ">: " << hash;
    return ss.str();
  }
  inline std::string MakePutReturn(const ustore::Hash& hash) {
    std::stringstream ss;
    ss << BOLD_GREEN("[SUCCESS: PUT] ") << "Version: " << hash;
    return ss.str();
  }

  ustore::WorkerClientService service_;
  std::shared_ptr<ustore::WorkerClient> wc_;
  std::shared_ptr<ustore::ObjectDB> os_;
};
}  // namespace seccask

extern std::shared_ptr<seccask::Ustore> g_ustore_ptr;
