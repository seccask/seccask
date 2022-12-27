# Use one of these commands to build the manifest for Bash:
#
# - make
# - make DEBUG=1
# - make SGX=1
# - make SGX=1 DEBUG=1
#
# Use `make clean` to remove Gramine-generated files.

ARCH_LIBDIR ?= /lib/$(shell gcc -dumpmachine)

APP_HOME ?= /home/mlcask/sgx/seccask2
PYZMQ_HOME ?= /home/mlcask/sgx/lib/pyzmq-23.1.0
SECCASK_BINARY_PATH ?= /home/mlcask/sgx/seccask2/build/bin/seccask

# Relative path to Gramine root and key for enclave signing
SGX_SIGNER_KEY ?= $(HOME)/.config/gramine/enclave-key.pem

EXEC_DIR = /bin

ifeq ($(DEBUG),1)
GRAMINE_LOG_LEVEL = trace
else
GRAMINE_LOG_LEVEL = error 
endif

.PHONY: all
all: seccask.manifest # python.manifest
ifeq ($(SGX),1)
all: seccask.manifest.sgx seccask.sig seccask.token # python.manifest.sgx python.sig python.token
endif

python.manifest: python.manifest.seccask.py39.toml
	gramine-manifest \
		-Dlog_level=$(GRAMINE_LOG_LEVEL) \
		-Darch_libdir=$(ARCH_LIBDIR) \
		-Dexecdir=$(EXEC_DIR) \
		-Dentrypoint=$(shell sh -c "command -v python") \
		-Dhome=$(HOME) \
		-Dapp_home=$(APP_HOME) \
		-Dpyzmq_home=$(PYZMQ_HOME) \
		$< >$@

python.manifest.sgx: python.manifest
	@test -s $(SGX_SIGNER_KEY) || \
	    { echo "SGX signer private key was not found, please specify SGX_SIGNER_KEY!"; exit 1; }
	gramine-sgx-sign \
		--key $(SGX_SIGNER_KEY) \
		--manifest $< \
		--output $@

python.sig: python.manifest.sgx

python.token: python.sig
	gramine-sgx-get-token --output $@ --sig $<


seccask.manifest: seccask.manifest.py39.toml
	gramine-manifest \
		-Dlog_level=$(GRAMINE_LOG_LEVEL) \
		-Darch_libdir=$(ARCH_LIBDIR) \
		-Dexecdir=$(EXEC_DIR) \
		-Dentrypoint=$(SECCASK_BINARY_PATH) \
		-Dhome=$(HOME) \
		-Dapp_home=$(APP_HOME) \
		-Dpyzmq_home=$(PYZMQ_HOME) \
		$< >$@

seccask.manifest.sgx: seccask.manifest
	@test -s $(SGX_SIGNER_KEY) || \
	    { echo "SGX signer private key was not found, please specify SGX_SIGNER_KEY!"; exit 1; }
	gramine-sgx-sign \
		--key $(SGX_SIGNER_KEY) \
		--manifest $< \
		--output $@

seccask.sig: seccask.manifest.sgx

seccask.token: seccask.sig
	gramine-sgx-get-token --output $@ --sig $<


ifeq ($(SGX),)
GRAMINE = gramine-direct
else
GRAMINE = gramine-sgx
endif

.PHONY: clean
clean:
	$(RM) *.manifest *.manifest.sgx *.token *.sig

.PHONY: distclean
distclean: clean
