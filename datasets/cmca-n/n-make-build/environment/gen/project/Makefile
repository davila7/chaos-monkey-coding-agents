# qs: the libqs statistics and expression library, colstat and qcalc.
# See docs/BUILDING.md for the targets and the rules the build follows.

.PHONY: all
all:

include mk/config.mk
include mk/gen.mk
include mk/lib.mk
include mk/tools.mk
include mk/check.mk
include mk/install.mk

all: gen lib tools $(PC_FILE)

.PHONY: clean
clean:
	rm -rf $(BUILD)
