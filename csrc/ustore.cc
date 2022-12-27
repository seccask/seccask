#include "seccask/ustore.h"

#include <pybind11/embed.h>
#include <pybind11/eval.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <spec/blob_store.h>
#include <utils/utils.h>

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>

#include "seccask/config.h"

static constexpr const char* kLedgerID = "DEFAULT";
static constexpr const char* kBranch = "DEFAULT";

static constexpr const char* kDefaultBasePath =
    "/home/seccask/extern/ustore_release";
static constexpr const char* kDefaultStoragePath =
    "/home/seccask/ustore_storage";

namespace py = pybind11;
using namespace pybind11::literals;

PYBIND11_EMBEDDED_MODULE(cpp_glassdb, m) {
  m.def(
      "get",
      [](std::string key, std::optional<std::string> branch,
         std::optional<std::string> hversion,
         std::optional<std::string> output_path) -> std::string {
        std::string branch_arg = branch.value_or(kBranch);
        std::string hversion_arg = hversion.value_or("");
        std::string output_path_arg = output_path.value_or("");
        return g_ustore_ptr->Get(key, branch_arg, hversion_arg,
                                 output_path_arg);
      },
      "key"_a.none(false), "branch"_a = py::none(), "hversion"_a = py::none(),
      "output_path"_a = py::none());
  m.def(
      "put",
      [](std::string key, std::string branch, std::optional<std::string> str,
         std::optional<std::string> input_path) -> std::string {
        std::string str_arg = str.value_or("");
        std::string input_path_arg = input_path.value_or("");
        return g_ustore_ptr->Put(key, branch, str_arg, input_path_arg);
      },
      "key"_a.none(false), "branch"_a.none(false), "str"_a = py::none(),
      "input_path"_a = py::none());
}

namespace seccask {
void Ustore::InitEnvVar() {
  std::filesystem::path base_path{
      Config::Get().GetStr("storage_ledgebase", "base_path", kDefaultBasePath)};
  std::filesystem::path storage_path{Config::Get().GetStr(
      "storage_ledgebase", "storage_path", kDefaultStoragePath)};

  util::log::Debug(kClassName, "Base path: {}", base_path.c_str());
  util::log::Debug(kClassName, "Storage path: {}", storage_path.c_str());

  setenv("USTORE_HOME", base_path.c_str(), 1);
  setenv("USTORE_BIN", (base_path / "bin").c_str(), 1);
  setenv("USTORE_CONF", (base_path / "conf").c_str(), 1);
  setenv("USTORE_CONF_DATA_DIR", storage_path.c_str(), 1);
  setenv("USTORE_CONF_FILE", (base_path / "conf/config.cfg").c_str(), 1);
  setenv("USTORE_CONF_HOST_FILE", (base_path / "conf/workers.lst").c_str(), 1);
  setenv("USTORE_LOG", (base_path / "log").c_str(), 1);

  util::log::Debug(kClassName, "Ustore environmental variables set");
}

std::string Ustore::Get(const std::string& key, const std::string& branch,
                        const std::string& hversion,
                        const std::string& output_path) {
  // ustore::WorkerClientService svc;
  // svc.Run();
  // ustore::WorkerClient wc = svc.CreateWorkerClient();
  // auto os = ustore::ObjectDB(&wc);

  ustore::Result<ustore::VMeta> reply;

  util::log::Debug(kClassName,
                   "GET key: {}, branch: {}, hversion: {}, output_path: {}",
                   key, branch, hversion, output_path);

  if (hversion.size() == ustore::Hash::kBase32Length) {
    // util::log::Debug(kClassName, "Use hversion to get");
    reply =
        os_->Get(ustore::Slice(kLedgerID), ustore::Hash::FromBase32(hversion));
  } else {
    // util::log::Debug(kClassName, "Use branch to get");
    reply = os_->Get(ustore::Slice(kLedgerID), ustore::Slice(branch));
  }
  // util::log::Debug(kClassName, "GET received reply");

  if (reply.stat != ustore::ErrorCode::kOK) {
    std::string result = MakeFailedReturn("GET", key, branch, reply.stat,
                                          ustore::Utils::ToString(reply.stat));
    util::log::Debug(kClassName, "GET Result: {}", result);
    return result;
  }

  // successfully get, verify result
  auto ledger = reply.value.Ledger();
  ustore::LedgerCache cache;
  auto digest = ledger.GetDigest().digest;
  auto proof = ledger.VerifyGet(ustore::Slice(key));
  auto res = proof.VerifyProof(digest, {ustore::Slice(key)}, &cache);
  if (!res) {
    std::string result =
        MakeFailedReturn("GET", key, branch, ustore::ErrorCode::kInvalidValue,
                         "verification failed");
    util::log::Debug(kClassName, "GET Result: {}", result);
    return result;
  }

  auto valstr = proof.GetValue(0);
  auto valslice = ustore::Slice(valstr);
  ustore::Chunk valchk(valslice.data());
  ustore::ValueNode valnode(&valchk);
  if (valstr.size() == 0 || valnode.GetValueSize() == 0) {
    std::string result =
        MakeFailedReturn("GET", key, branch, ustore::ErrorCode::kKeyNotExists,
                         "key does not exist");
    util::log::Debug(kClassName, "GET Result: {}", result);
    return result;
  }

  if (valnode.type() == ustore::UType::kLedgerString) {
    // get string
    std::string result =
        MakeStringGetReturn(key, branch, valnode.type(), valnode.GetValue());
    util::log::Debug(kClassName, "GET Result: {}", result);
    return result;
  } else {
    // get file
    auto blob_hash = ustore::Hash(valnode.GetValue());
    auto chunk_loader = std::make_shared<ustore::ClientChunkLoader>(
        wc_.get(), ustore::Slice(key));
    ustore::VBlob blob(chunk_loader, blob_hash);
    std::string blobstr;
    blob.Read(0, blob.size(), &blobstr);
    std::ofstream ofs(output_path);
    ofs << blobstr;
    ofs.close();

    std::string result =
        MakeBlobGetReturn(key, branch, valnode.type(), blob_hash);
    util::log::Debug(kClassName, "GET Result: {}", result);
    return result;
  }
}

std::string Ustore::Put(const std::string& key, const std::string& branch,
                        const std::string& str, const std::string& input_path) {
  // ustore::WorkerClientService svc;
  // svc.Run();
  // ustore::WorkerClient wc = svc.CreateWorkerClient();
  // auto os = ustore::ObjectDB(&wc);

  std::string value;
  ustore::UType type;

  if (str.size() == 0) {
    // put file
    if (!std::filesystem::is_regular_file(std::filesystem::path(input_path))) {
      std::string result = MakeFileNotFoundReturn(input_path);
      util::log::Debug(kClassName, "PUT Result: {}", result);
      return result;
    }
    std::ifstream ifs(input_path);
    std::stringstream ss;
    ss << ifs.rdbuf();
    value = ss.str();
    type = ustore::UType::kLedgerBlob;
  } else {
    // put str
    value = str;
    type = ustore::UType::kLedgerString;
  }

  ustore::Result<ustore::Hash> reply;
  reply = os_->Put(
      ustore::Slice(kLedgerID),
      ustore::VLedger({ustore::Slice(key)}, {ustore::Slice(value)}, type),
      ustore::Slice(branch));

  if (reply.stat != ustore::ErrorCode::kOK) {
    std::string result = MakeFailedReturn("PUT", key, branch, reply.stat,
                                          ustore::Utils::ToString(reply.stat));
    util::log::Debug(kClassName, "PUT Result: {}", result);
    return result;

  } else {
    std::string result = MakePutReturn(reply.value);
    util::log::Debug(kClassName, "PUT Result: {}", result);
    return result;
  }
}

}  // namespace seccask