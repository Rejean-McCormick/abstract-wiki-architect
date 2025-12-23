
# GF Compiler Settings
# We add paths for German (deu) and Spanish (spa)
GF_FLAGS = -path gf-rgl/src/api:gf-rgl/src/abstract:gf-rgl/src/common:gf-rgl/src/prelude:gf-rgl/src/english:gf-rgl/src/french:gf-rgl/src/german:gf-rgl/src/spanish:gf/ -output-dir=gf

# Files to compile
SOURCES = gf/WikiEng.gf gf/WikiFra.gf gf/WikiGer.gf gf/WikiSpa.gf

all:
	@echo 'Compiling 4 Tier-1 Languages...'
	gf -make $(GF_FLAGS) $(SOURCES)
	@echo 'Build Complete.'

clean:
	rm -f gf/*.gfo gf/*.pgf

