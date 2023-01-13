OPENSSL := openssl
OPENSSL_VERS := 1.1.1q
OPENSSL_DIR := $(OPENSSL)-$(OPENSSL_VERS)
# Increase this to enforce a recreation of the build cache
OPENSSL_BUILD_ID := 3

OPENSSL_UNPACK := $(BUILD_HELPER_DIR)/$(OPENSSL_DIR)-unpack
OPENSSL_BUILD := $(BUILD_HELPER_DIR)/$(OPENSSL_DIR)-build
OPENSSL_INTERMEDIATE_INSTALL := $(BUILD_HELPER_DIR)/$(OPENSSL_DIR)-install-intermediate
OPENSSL_CACHE_PKG_PROCESS := $(BUILD_HELPER_DIR)/$(OPENSSL_DIR)-cache-pkg-process
OPENSSL_INSTALL := $(BUILD_HELPER_DIR)/$(OPENSSL_DIR)-install

OPENSSL_INSTALL_DIR := $(INTERMEDIATE_INSTALL_BASE)/$(OPENSSL_DIR)
OPENSSL_BUILD_DIR := $(PACKAGE_BUILD_DIR)/$(OPENSSL_DIR)
#OPENSSL_WORK_DIR := $(PACKAGE_WORK_DIR)/$(OPENSSL_DIR)

# Executed from enterprise/core/src/Makefile.am
$(OPENSSL)-build-library: $(BUILD_HELPER_DIR) $(OPENSSL_CACHE_PKG_PROCESS)

# Used by Python/Python.make
ifeq ($(DISTRO_CODE),el8)
PACKAGE_OPENSSL_DESTDIR := /usr
else
PACKAGE_OPENSSL_DESTDIR := $(OPENSSL_INSTALL_DIR)
PACKAGE_OPENSSL_LDFLAGS := -L$(PACKAGE_OPENSSL_DESTDIR)/lib
PACKAGE_OPENSSL_LD_LIBRARY_PATH := $(PACKAGE_OPENSSL_DESTDIR)/lib
PACKAGE_OPENSSL_INCLUDE_PATH := $(PACKAGE_OPENSSL_DESTDIR)/include
endif

ifeq ($(DISTRO_CODE),el8)
$(OPENSSL_BUILD): $(OPENSSL_UNPACK)
	$(TOUCH) $@
else
$(OPENSSL_BUILD): $(OPENSSL_UNPACK)
	cd $(OPENSSL_BUILD_DIR) && \
	    ./config --prefix=$(OMD_ROOT) \
                 --openssldir=$(OMD_ROOT)/etc/ssl \
                 -Wl,-rpath,$(OMD_ROOT)/lib \
                 enable-md2 \
                 no-tests
	$(MAKE) -C $(OPENSSL_BUILD_DIR) -j6
	$(TOUCH) $@
endif

OPENSSL_CACHE_PKG_PATH := $(call cache_pkg_path,$(OPENSSL_DIR),$(OPENSSL_BUILD_ID))

$(OPENSSL_CACHE_PKG_PATH):
	$(call pack_pkg_archive,$@,$(OPENSSL_DIR),$(OPENSSL_BUILD_ID),$(OPENSSL_INTERMEDIATE_INSTALL))

$(OPENSSL_CACHE_PKG_PROCESS): $(OPENSSL_CACHE_PKG_PATH)
	$(call unpack_pkg_archive,$(OPENSSL_CACHE_PKG_PATH),$(OPENSSL_DIR))
	$(call upload_pkg_archive,$(OPENSSL_CACHE_PKG_PATH),$(OPENSSL_DIR),$(OPENSSL_BUILD_ID))
	$(TOUCH) $@

# This is horrible...
ifeq ($(DISTRO_CODE),el8)
$(OPENSSL_INTERMEDIATE_INSTALL): $(OPENSSL_BUILD)
	$(MKDIR) $(OPENSSL_INSTALL_DIR)
	$(TOUCH) $@
else
$(OPENSSL_INTERMEDIATE_INSTALL): $(OPENSSL_BUILD)
	$(MKDIR) $(OPENSSL_INSTALL_DIR)
	$(MAKE) -C $(OPENSSL_BUILD_DIR) DESTDIR=$(OPENSSL_INSTALL_DIR) install_sw
	$(MAKE) -C $(OPENSSL_BUILD_DIR) DESTDIR=$(OPENSSL_INSTALL_DIR) install_ssldirs
	$(MKDIR) $(OPENSSL_INSTALL_DIR)/skel
	$(RSYNC) $(OPENSSL_INSTALL_DIR)/$(OMD_ROOT)/etc $(OPENSSL_INSTALL_DIR)/skel
	$(RM) -r $(OPENSSL_INSTALL_DIR)/$(OMD_ROOT)/etc
	$(RSYNC) $(OPENSSL_INSTALL_DIR)/$(OMD_ROOT)/* $(OPENSSL_INSTALL_DIR)
	$(RM) -r $(OPENSSL_INSTALL_DIR)/omd
	$(TOUCH) $@
endif

ifeq ($(DISTRO_CODE),el8)
$(OPENSSL_INSTALL): $(OPENSSL_CACHE_PKG_PROCESS)
	$(TOUCH) $@
else
$(OPENSSL_INSTALL): $(OPENSSL_CACHE_PKG_PROCESS)
	$(RSYNC) $(OPENSSL_INSTALL_DIR)/ $(DESTDIR)$(OMD_ROOT)/
	$(TOUCH) $@
endif
