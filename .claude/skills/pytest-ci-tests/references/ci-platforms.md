# CI platforms: where the file is, and how to add pytest

Use the snippets as a shape, not as text to paste. Always copy the Python
version, image, install command and triggers from the existing file. Replace
`python -m pytest` with the project's own command (`uv run pytest`,
`poetry run pytest`, `tox`, …).

## Contents

- How to find CI files
- GitHub Actions
- GitLab CI
- Azure Pipelines
- Bitbucket Pipelines
- CircleCI
- Jenkins
- Travis CI
- Other platforms
- Test reports (optional)

## How to find CI files

Search the full repository, not only the root:

```bash
find . -path ./node_modules -prune -o -path ./.venv -prune -o \( \
  -path './.github/workflows/*' -o -name '.gitlab-ci.yml' -o -path './.gitlab/*' \
  -o -name 'azure-pipelines*.yml' -o -path './.azure-pipelines/*' -o -path './.azure/*' -o -path './.pipelines/*' \
  -o -name 'bitbucket-pipelines.yml' -o -path './.circleci/*' -o -name 'Jenkinsfile*' \
  -o -name '.travis.yml' -o -name '.drone.yml' -o -name '.woodpecker.yml' -o -path './.woodpecker/*' \
  -o -path './.buildkite/*' -o -name 'buildspec*.yml' -o -name 'cloudbuild*.yaml' -o -name 'cloudbuild*.yml' \
  -o -name 'appveyor.yml' -o -name '.appveyor.yml' -o -name 'codemagic.yaml' -o -path './.tekton/*' \
  -o -path './.semaphore/*' -o -name 'wercker.yml' \) -print
```

Then search those files for the test command:

```bash
grep -nE 'pytest|py\.test|tox|nox|make +test|just +test|hatch +test' <files>
```

## GitHub Actions

Files: `.github/workflows/*.yml` or `*.yaml`.

Add a step after the install step of the job that sets up Python:

```yaml
      - name: Run tests
        run: python -m pytest -ra
```

If no job sets up Python, add a job and copy `on:` from the file:

```yaml
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[test]"
      - name: Run tests
        run: python -m pytest -ra
```

For uv, use `astral-sh/setup-uv` and `uv sync --dev`, then `uv run pytest`.
If the workflow uses a `matrix` of Python versions, keep the matrix.

## GitLab CI

File: `.gitlab-ci.yml`, plus files it `include:`s.

Add a job in the stage that already tests or checks code. If no such stage
exists, add `test` to `stages:`.

```yaml
pytest:
  stage: test
  image: python:3.12
  script:
    - pip install -e ".[test]"
    - python -m pytest -ra --junitxml=report.xml
  artifacts:
    when: always
    reports:
      junit: report.xml
```

If the file has a hidden template job (a name that starts with `.`) or
`default:` with the image and install, use `extends:` and do not repeat
them. Copy `rules:` or `only:` from the other jobs.

## Azure Pipelines

Files: `azure-pipelines.yml`, `azure-pipelines/*.yml`, `.azure-pipelines/`,
`.pipelines/`, or a path set in the Azure DevOps project.

Add a step after the install step:

```yaml
  - script: python -m pytest -ra --junitxml=test-results.xml
    displayName: Run tests

  - task: PublishTestResults@2
    condition: succeededOrFailed()
    inputs:
      testResultsFiles: test-results.xml
      testRunTitle: Python tests
```

If the file uses `stages:` and `jobs:`, add the steps to the job that
builds the Python code. If it uses `template:` files, edit the template
that holds the steps. Keep `UsePythonVersion@0` as it is.

## Bitbucket Pipelines

File: `bitbucket-pipelines.yml`.

Add a line to the `script:` of the step that installs the dependencies:

```yaml
        script:
          - pip install -e ".[test]"
          - python -m pytest -ra --junitxml=test-reports/report.xml
```

Bitbucket reads JUnit files from `test-reports/` with no more
configuration. Add the line to each pipeline (`default`, `branches`,
`pull-requests`) that builds the code.

## CircleCI

File: `.circleci/config.yml`.

Add a step to the job that installs the dependencies:

```yaml
      - run:
          name: Run tests
          command: python -m pytest -ra --junitxml=test-results/junit.xml
      - store_test_results:
          path: test-results
```

If the config uses the `circleci/python` orb, keep it. Make sure the job is
listed in a `workflows:` entry.

## Jenkins

File: `Jenkinsfile` (declarative or scripted).

Declarative: add a stage after the install stage:

```groovy
        stage('Test') {
            steps {
                sh 'python -m pytest -ra --junitxml=test-results.xml'
            }
            post {
                always {
                    junit 'test-results.xml'
                }
            }
        }
```

Use `bat` instead of `sh` if the other stages use `bat`. Keep the
`agent` and the environment as they are.

## Travis CI

File: `.travis.yml`.

Set or extend `script:`:

```yaml
script:
  - python -m pytest -ra
```

If `script:` already runs other checks, add pytest as a new item.

## Other platforms

The rule is the same for each one: find the step or job that installs the
Python dependencies, and add the pytest command after it.

| Platform | File | Where to add the command |
| --- | --- | --- |
| Drone | `.drone.yml` | `commands:` of the Python step |
| Woodpecker | `.woodpecker.yml`, `.woodpecker/*.yml` | `commands:` of the Python step |
| Buildkite | `.buildkite/pipeline.yml` | a new `command:` step |
| AWS CodeBuild | `buildspec.yml` | `phases.build.commands` |
| Google Cloud Build | `cloudbuild.yaml` | a new step with a Python image |
| AppVeyor | `appveyor.yml` | `test_script:` |
| Semaphore | `.semaphore/semaphore.yml` | `commands:` of a job |
| Tekton | `.tekton/*.yaml` | a task step |

## Test reports (optional)

Add a JUnit report (`--junitxml=...`) only when the platform shows it
(GitLab, Azure, Bitbucket, CircleCI, Jenkins), or when the file already
publishes reports for other jobs. Do not add coverage upload or new secrets.