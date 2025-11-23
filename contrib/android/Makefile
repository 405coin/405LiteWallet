SHELL := /bin/bash
PYTHON = python3


export LC_ALL             := C
export TZ                 := UTC
ifndef ELEC_APK_USE_CURRENT_TIME
    export SOURCE_DATE_EPOCH  := $(shell git log -1 --pretty=%ct)
else






    export SOURCE_DATE_EPOCH  := $(shell date +%s)
endif
export PYTHONHASHSEED     := $(SOURCE_DATE_EPOCH)
export BUILD_DATE         := $(shell LC_ALL=C TZ=UTC date +'%b %e %Y' -d @$(SOURCE_DATE_EPOCH))
export BUILD_TIME         := $(shell LC_ALL=C TZ=UTC date +'%H:%M:%S' -d @$(SOURCE_DATE_EPOCH))


.PHONY: apk clean

prepare:


	@cp buildozer_$(ELEC_APK_GUI).spec ../../buildozer.spec
	@cp ../../run_405litewallet ../../main.py
apk:
	@make prepare
	@-cd ../..; buildozer android debug
	@make clean
release:
	@make prepare
	@-cd ../..; buildozer android release
	@make clean
clean:


	@-rm ../../main.py

	@-rm ../../buildozer.spec
