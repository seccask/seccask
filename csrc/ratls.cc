#include "seccask/ratls.h"

#include <dlfcn.h>
#include <openssl/x509.h>

#include "seccask/config.h"
#include "seccask/util.h"

namespace util = seccask::util;
using seccask::g_expected_mrenclave;
using seccask::g_expected_mrsigner;
using seccask::RATLS;

/* RA-TLS: on server, only need ra_tls_create_key_and_crt_der() to create
 * keypair and X.509 cert */
int (*ra_tls_create_key_and_crt_der_f)(uint8_t** der_key, size_t* der_key_size,
                                       uint8_t** der_crt, size_t* der_crt_size);

/* RA-TLS: on client, only need to register ra_tls_verify_callback_der() for
 * cert verification */
int (*ra_tls_verify_callback_der_f)(uint8_t* der_crt, size_t der_crt_size);

/* RA-TLS: if specified in command-line options, use our own callback to verify
 * SGX measurements */
void (*ra_tls_set_measurement_callback_f)(int (*f_cb)(const char* mrenclave,
                                                      const char* mrsigner,
                                                      const char* isv_prod_id,
                                                      const char* isv_svn));

namespace seccask {
int custom_tls_verification_callback(const char* mrenclave,
                                     const char* mrsigner,
                                     const char* isv_prod_id,
                                     const char* isv_svn) {
  std::string mrenclave_hex_str;
  std::string mrsigner_hex_str;
  boost::algorithm::hex_lower(mrenclave, mrenclave + 32,
                              std::back_inserter(mrenclave_hex_str));
  boost::algorithm::hex_lower(mrsigner, mrsigner + 32,
                              std::back_inserter(mrsigner_hex_str));

  util::log::Debug(RATLS::kClassName, "Receiving quote with values: <{} {}>",
                   mrenclave_hex_str, mrsigner_hex_str);

  assert(mrenclave && mrsigner);

  if (memcmp(mrenclave, g_expected_mrenclave, sizeof(g_expected_mrenclave))) {
    util::log::Error(RATLS::kClassName, "At line {}: mrenclave mismatch",
                     __LINE__);
    throw std::runtime_error("mrenclave mismatch");
  }

  if (memcmp(mrsigner, g_expected_mrsigner, sizeof(g_expected_mrenclave))) {
    util::log::Error(RATLS::kClassName, "At line {}: mrsigner mismatch",
                     __LINE__);
    throw std::runtime_error("mrsigner mismatch");
  }

  return 0;
}

bool RATLS::PrintCertOnly(bool /*preverified*/,
                          boost::asio::ssl::verify_context& ctx) {
  // The verify callback can be used to check whether the certificate that is
  // being presented is valid for the peer. For example, RFC 2818 describes
  // the steps involved in doing this for HTTPS. Consult the OpenSSL
  // documentation for more details. Note that the callback is called once
  // for each certificate in the certificate chain, starting from the root
  // certificate authority.
  char subject_name[256];
  X509* cert = X509_STORE_CTX_get_current_cert(ctx.native_handle());
  X509_NAME_oneline(X509_get_subject_name(cert), subject_name, 256);
  util::log::Info(kClassName, "Verifying {}", subject_name);
  return true;
}

bool RATLS::Verify(bool /*preverified*/,
                   boost::asio::ssl::verify_context& ctx) {
  timespec time1, time2;
  clock_gettime(CLOCK_REALTIME, &time1);

  char subject_name[256];
  uint8_t* cert_der = nullptr;
  X509* cert = X509_STORE_CTX_get_current_cert(ctx.native_handle());
  X509_NAME_oneline(X509_get_subject_name(cert), subject_name, 256);
  util::log::Info(kClassName, "Verifying {}", subject_name);

  int len = i2d_X509(cert, &cert_der);
  if (len < 0) {
    util::log::Error(kClassName, "At line {}: {}", __LINE__,
                     "X.509 DER creation failed");
    return false;
  }
  util::log::Debug(kClassName,
                   "At line {}: X.509 DER format cert created with length {}",
                   __LINE__, len);
  int is_malicious = ra_tls_verify_callback_der_f(cert_der, len);
  util::log::Info(kClassName, "Result of RA-TLS verification: {}",
                  !is_malicious);
  OPENSSL_free(cert_der);

  clock_gettime(CLOCK_REALTIME, &time2);
  timespec duration = util::TimeDiff(time1, time2);
  util::log::Debug(kClassName, "Time diff for RA-TLS verification: {}:{}",
                   duration.tv_sec, duration.tv_nsec);

  return !is_malicious;
}

void RATLS::DoInitExpectedValues() {
  std::string mrenclave = boost::algorithm::unhex(Config::MREnclave());
  std::copy(mrenclave.begin(), mrenclave.end(), g_expected_mrenclave);
  std::string mrsigner =
      boost::algorithm::unhex(std::string(Config::MRSigner()));
  std::copy(mrsigner.begin(), mrsigner.end(), g_expected_mrsigner);
}

void RATLS::DoInitQuoteGeneration() {
  static bool is_initialized = false;
  if (is_initialized) return;

  timespec time1, time2;
  clock_gettime(CLOCK_REALTIME, &time1);

  char attestation_type_str[32] = {0};
  int ret =
      util::ReadFile("/dev/attestation/attestation_type", attestation_type_str,
                     sizeof(attestation_type_str) - 1);
  if (ret < 0 && ret != -ENOENT) {
    util::log::Error(
        kClassName,
        "User requested RA-TLS attestation but cannot read SGX-specific file "
        "/dev/attestation/attestation_type");
    return;
  }

  ra_tls_attest_lib_ = dlopen("libra_tls_attest.so", RTLD_LAZY);
  if (!ra_tls_attest_lib_) {
    util::log::Error(kClassName,
                     "User requested RA-TLS attestation but cannot find lib\n");
    return;
  }

  char* error;
  ra_tls_create_key_and_crt_der_f =
      reinterpret_cast<int (*)(uint8_t**, size_t*, uint8_t**, size_t*)>(
          dlsym(ra_tls_attest_lib_, "ra_tls_create_key_and_crt_der"));
  if ((error = dlerror()) != NULL) {
    util::log::Error(kClassName, error);
    return;
  }

  util::log::Debug(kClassName,
                   "Creating the RA-TLS server cert and key (using \"{}\" as "
                   "attestation type)...",
                   attestation_type_str);
  fflush(stdout);

  static uint8_t* der_crt = NULL;
  static size_t der_crt_size = 0;
  ret = (*ra_tls_create_key_and_crt_der_f)(&der_key_, &der_key_size_, &der_crt,
                                           &der_crt_size);
  if (ret != 0) {
    util::log::Error(kClassName,
                     "failed! ra_tls_create_key_and_crt_der returned {}", ret);
    return;
  }

  const uint8_t* der_crt_ptr = der_crt;
  x509_cert_ = ::d2i_X509(NULL, &der_crt_ptr, der_crt_size);

  char subject_name[256];
  ::X509_NAME_oneline(X509_get_subject_name(x509_cert_), subject_name, 256);
  util::log::Info(kClassName, "Creating certificate {}", subject_name);

  util::log::Debug(kClassName, "Quote generation initialized");
  is_initialized = true;

  clock_gettime(CLOCK_REALTIME, &time2);
  timespec duration = util::TimeDiff(time1, time2);
  util::log::Debug(kClassName, "Time diff for RA-TLS quote generation: {}:{}",
                   duration.tv_sec, duration.tv_nsec);
}

void RATLS::DoInitVerification() {
  static bool is_initialized = false;
  if (is_initialized) return;

  timespec time1, time2;
  clock_gettime(CLOCK_REALTIME, &time1);

  char* error;

  void* helper_sgx_urts_lib = dlopen("libsgx_urts.so", RTLD_NOW | RTLD_GLOBAL);
  if (!helper_sgx_urts_lib) {
    util::log::Error(kClassName, "At line {}: {}", dlerror());
    util::log::Error(
        kClassName,
        "User requested RA-TLS verification with DCAP but cannot find "
        "libsgx_urts.so");
    return;
  }

  ra_tls_verify_lib_ = dlopen("libra_tls_verify_dcap.so", RTLD_LAZY);
  if (!ra_tls_verify_lib_) {
    util::log::Error(kClassName, "At line {}: {}", dlerror());
    util::log::Error(
        kClassName,
        "User requested RA-TLS verification with DCAP but cannot find "
        "libra_tls_verify_dcap.so");
    return;
  }

  ra_tls_verify_callback_der_f = reinterpret_cast<int (*)(uint8_t*, size_t)>(
      dlsym(ra_tls_verify_lib_, "ra_tls_verify_callback_der"));
  if ((error = dlerror()) != NULL) {
    util::log::Error(kClassName, "At line {}: {}", __LINE__, error);
    return;
  }

  ra_tls_set_measurement_callback_f = reinterpret_cast<void (*)(
      int (*)(const char*, const char*, const char*, const char*))>(
      dlsym(ra_tls_verify_lib_, "ra_tls_set_measurement_callback"));
  if ((error = dlerror()) != NULL) {
    util::log::Error(kClassName, "At line {}: {}", __LINE__, error);
    return;
  }

  (*ra_tls_set_measurement_callback_f)(
      &seccask::custom_tls_verification_callback);

  util::log::Debug(kClassName, "Quote verification initialized");
  is_initialized = true;

  clock_gettime(CLOCK_REALTIME, &time2);
  timespec duration = util::TimeDiff(time1, time2);
  util::log::Debug(kClassName,
                   "Time diff for registering RA-TLS quote verification: {}:{}",
                   duration.tv_sec, duration.tv_nsec);
}

void RATLS::DoSetupSSLContext(boost::asio::ssl::context& ctx) {
  timespec time1, time2;
  clock_gettime(CLOCK_REALTIME, &time1);

  int ret;

  ::SSL_CTX_set_options(ctx.native_handle(), SSL_OP_NO_SSLv2 | SSL_OP_NO_SSLv3 |
                                                 SSL_OP_NO_COMPRESSION |
                                                 SSL_OP_NO_TICKET);

  ret = ::SSL_CTX_set1_groups_list(ctx.native_handle(), "X25519:X448");
  if (ret != 1) {
    util::log::Error(kClassName, "failed! SSL_CTX_set1_groups_list returned {}",
                     ret);
    util::log::Error(kClassName, util::OpenSSLError2String());
    return;
  }

  ret = ::SSL_CTX_set1_sigalgs_list(ctx.native_handle(),
                                    "ECDSA+SHA256:RSA+SHA256");
  if (ret != 1) {
    util::log::Error(kClassName,
                     "failed! SSL_CTX_set1_sigalgs_list returned {}", ret);
    util::log::Error(kClassName, util::OpenSSLError2String());
    return;
  }

  ret = ::SSL_CTX_use_certificate(ctx.native_handle(), x509_cert_);
  if (ret != 1) {
    util::log::Error(kClassName,
                     "failed! SSL_CTX_use_certificate_ASN1 returned {}", ret);
    util::log::Error(kClassName, util::OpenSSLError2String());
    return;
  }

  ret = ::SSL_CTX_use_PrivateKey_ASN1(EVP_PKEY_RSA, ctx.native_handle(),
                                      der_key_, der_key_size_);
  if (ret != 1) {
    util::log::Error(kClassName,
                     "failed! SSL_CTX_use_PrivateKey_ASN1 returned {}", ret);
    util::log::Error(kClassName, util::OpenSSLError2String());
    return;
  }

  util::log::Debug(kClassName, "SSL context setup complete");

  clock_gettime(CLOCK_REALTIME, &time2);
  timespec duration = util::TimeDiff(time1, time2);
  util::log::Debug(kClassName, "Time diff for RA-TLS SSL context setup: {}:{}",
                   duration.tv_sec, duration.tv_nsec);
}

}  // namespace seccask