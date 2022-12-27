#include "seccask/encfs.h"

#include <cxxabi.h>
#include <openssl/sha.h>

#include <boost/algorithm/hex.hpp>

#include "seccask/util.h"

extern "C" {
unsigned char *g_component_key = NULL; /*< 256-bit key */
}

namespace seccask {
namespace encfs {

inline static constexpr const char *kClassName = "EncryptedStorage";

static void Destroy() {
  free(g_component_key);
  util::log::Debug(kClassName, "Encrypted storage destroyed");
}

static void SHA256(const std::string &key, unsigned char *outputBuffer) {
  SHA256_CTX sha256;
  SHA256_Init(&sha256);
  SHA256_Update(&sha256, key.c_str(), key.size());
  SHA256_Final(outputBuffer, &sha256);
}

void InitWithKey(const std::string &component_key) {
  if (g_component_key != NULL) {
    Destroy();
  }

  g_component_key = (unsigned char *)malloc(SHA256_DIGEST_LENGTH);
  SHA256(component_key, g_component_key);

  char key_hex[2 * SHA256_DIGEST_LENGTH + 1] = {0};
  boost::algorithm::hex((const char *)g_component_key,
                        (const char *)g_component_key + SHA256_DIGEST_LENGTH,
                        key_hex);
  util::log::Debug(kClassName, "Encrypted storage initialized with {}",
                   key_hex);
}
}  // namespace encfs
}  // namespace seccask