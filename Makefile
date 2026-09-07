.PHONY: validate validate-skills validate-snippets sync package help

help:
	@echo "Available targets:"
	@echo "  validate          Run all validation checks (skills + snippets)"
	@echo "  validate-skills   Catalog/manifest/layer/reference checks"
	@echo "  validate-snippets Code-block syntax checks across skills/"
	@echo "  sync              Regenerate plugin manifests from catalog.json"
	@echo "  package           Build per-skill zips for web upload into dist/"

validate: validate-skills validate-snippets

validate-skills:
	cd scripts && python3 validate_skills.py

validate-snippets:
	python3 tests/validate_snippets.py

sync:
	cd scripts && python3 sync_manifests.py

package:
	cd scripts && python3 package_skills.py --clean
