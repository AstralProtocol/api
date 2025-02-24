# Python Environment Setup with Poetry

This document provides step-by-step instructions for setting up the Python environment for the project using [Poetry](https://python-poetry.org/). Poetry will manage dependencies, virtual environments, and build configurations, ensuring consistency across development, testing, and deployment.

## 1. Install Poetry

- **Linux/macOS:**  
  Open a terminal and run:
  ```bash
  curl -sSL https://install.python-poetry.org | python3 -
  ```
- **Windows:**  
  Use PowerShell (run as Administrator) and execute:
  ```powershell
  (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
  ```
- **Verify Installation:**  
  Check that Poetry is installed by running:
  ```bash
  poetry --version
  ```

## 2. Project Setup

- **Clone the Repository:**  
  If you haven’t already, clone the project repository:
  ```bash
  git clone https://your.repo.url.git
  cd your-project-directory
  ```

- **Initialize the Project with Poetry:**  
  If the project is already configured with a `pyproject.toml`, simply run:
  ```bash
  poetry install
  ```
  This command will:
  - Create a virtual environment (if one doesn’t exist).
  - Install all dependencies as specified in the `pyproject.toml` file.

## 3. Managing Dependencies

- **Adding a Dependency:**  
  To add a new package to your project, use:
  ```bash
  poetry add <package-name>
  ```
- **Adding a Dev Dependency:**  
  For development-only dependencies (e.g., pytest, Black, isort, Flake8, mypy), use:
  ```bash
  poetry add --dev <package-name>
  ```

## 4. Activating the Virtual Environment

- **Shell Access:**  
  To activate the virtual environment managed by Poetry, run:
  ```bash
  poetry shell
  ```
- **Running Commands Within the Environment:**  
  Alternatively, prefix commands with `poetry run`. For example:
  ```bash
  poetry run python your_script.py
  poetry run pytest
  ```

## 5. Pre-commit Hooks & Code Quality

- **Set Up Pre-commit Hooks:**  
  The repository includes a `.pre-commit-config.yaml` file. Install pre-commit hooks by running:
  ```bash
  poetry run pre-commit install
  ```
- **Running Pre-commit Checks Manually:**  
  To run all pre-commit hooks against all files:
  ```bash
  poetry run pre-commit run --all-files
  ```

## 6. Running Tests

- **Using pytest:**  
  Run tests with:
  ```bash
  poetry run pytest
  ```

## 7. Additional Tools

- **Formatting and Linting:**  
  The project uses Black for formatting, isort for import sorting, and Flake8 for linting. These tools are configured in the pre-commit hooks and can also be run manually:
  ```bash
  poetry run black .
  poetry run isort .
  poetry run flake8
  ```
- **Static Type Checking:**  
  To run mypy for static type checking:
  ```bash
  poetry run mypy .
  ```

---

By following these instructions, you will set up a consistent Python development environment using Poetry. This ensures that all developers and CI/CD pipelines use the same dependencies and configurations, reducing integration issues and simplifying maintenance. 