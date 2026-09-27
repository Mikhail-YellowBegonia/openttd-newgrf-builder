PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
NMLC ?= $(if $(wildcard .venv/bin/nmlc),.venv/bin/nmlc,nmlc)
NML_SOURCE := building/building.nml
NML_RESOURCES := building/resources/nml

rebuild: clean all

all: building.grf

validate:
	$(PYTHON) -m tools.asset_pipeline validate

lock: validate
	$(PYTHON) -m tools.asset_pipeline lock

template:
	$(PYTHON) -m tools.template --output templates/isometric-1x1-h8 --footprint 1x1 --height 8

work-order:
	$(PYTHON) -m tools.work_order --help

building: clean_building building.grf

clean_building:
	rm -f building.grf $(NML_SOURCE)
	rm -rf $(NML_RESOURCES)

clean:
	rm -f *.grf

doc.building:
	$(PYTHON) -m house.gen doc

building.grf: FORCE
	$(PYTHON) -m house.nml_gen --manifest assets/manifest.csv --output $(NML_SOURCE) --resources $(NML_RESOURCES)
	$(NMLC) -l house/lang --default-lang=english-uk.lng $(NML_SOURCE) --grf $@

building.grf.sha256: building.grf
	shasum -a 256 building.grf > building.grf.sha256

package: validate lock building.grf building.grf.sha256

FORCE:
