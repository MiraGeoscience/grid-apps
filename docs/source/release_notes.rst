Release Notes
=============

Release 0.2.0 (2026-06-04)
--------------------------

- Line up Drivers with base.Driver class
- Update minimum requirement to python >=3.12, <3.15 and numpy 2.*
- Fix label capitalization
- Refresh screenshots of UIJsons in docs


Release 0.1.0 (2026-01-06)
--------------------------

**(First release)**

New features
^^^^^^^^^^^^

- Transfer block model creation to grid-apps
- Update package with python-conda-template
- Fixup README by using regular double quotes
- Exclude RUF005
- Update input variables in github shared workflows
- Relock on geoapps-utils@release/0.4.0, allow py 3.12
- Automatically publish python package on Artifactory
- Add a test to check consistency between conda and pip
- Update copyright date to 2025
- Build conda package faster with rattler-build
- Specify jira component in issue_to_jira
- Complete package readme and description
- Align license terms in grid-apps
- Environment for coming pre-release
- Add BlockModel to TensorMesh utility in grid-apps
- Convert BlockModel to octree
- Refinement not working on float values
- Change label on 'objects' for Block Model
- Add workflow for zizmor and apply recommendations
- Use Poetry 2 and have pyproject.toml checked by pre-commit
- Migrate octree-creation-app to grid-app
- Auto versioning of python packages
- Crash on MT survey as input for mesh creation
- Possible crash with auto-meshing for potential fields inversion
- Configure newer zizmor workflows
- No need for jinja nor toml in tests
- Packages get published with 0.0.0 value for __version__
- Fix deprecation warning on grid-apps
