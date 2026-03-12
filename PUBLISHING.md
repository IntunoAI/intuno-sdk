# Publishing the Intuno SDK

This guide provides instructions on how to publish the `intuno-sdk` to both GitHub and PyPI.

## Publishing to GitHub

Publishing the code to a GitHub repository allows for collaboration, version control, and public visibility.

1.  **Initialize a Git repository:**
    If you haven't already, initialize a Git repository in the `intuno_sdk` directory.
    ```bash
    cd /path/to/intuno_sdk
    git init -b main
    ```

2.  **Add and Commit Files:**
    Add all the SDK files to staging and make your first commit.
    ```bash
    git add .
    git commit -m "Initial commit: Scaffold Intuno SDK"
    ```

3.  **Create a Repository on GitHub:**
    Go to [GitHub](https://github.com) and create a new public repository. Give it a name like `intuno-sdk`. Do not initialize it with a README or .gitignore, as we have already created those.

4.  **Link and Push:**
    Link your local repository to the remote one on GitHub and push your code.
    ```bash
    # Replace <YOUR_USERNAME> and <YOUR_REPO_NAME> with your details
    git remote add origin https://github.com/<YOUR_USERNAME>/<YOUR_REPO_NAME>.git
    git push -u origin main
    ```

## Publishing to PyPI

Publishing the package to the Python Package Index (PyPI) makes it publicly available to be installed via `pip`. This project is set up to use [Poetry](https://python-poetry.org/) for easy packaging and publishing.

### Prerequisites

1.  **Create a PyPI Account:**
    If you don't have one, create an account on [PyPI](https://pypi.org/).

2.  **Get an API Token:**
    After logging in, go to your "Account settings" and create a new API token. When creating the token, scope it to the specific project (`intuno-sdk`) if you wish, or to your entire account. **Copy this token immediately**, as you will not be able to see it again.

### Publishing Steps

1.  **Configure Poetry:**
    Configure Poetry to use your PyPI API token. This command will store the token securely in Poetry's configuration.
    ```bash
    poetry config pypi-token.pypi <YOUR_PYPI_API_TOKEN>
    ```

2.  **Check the Package Metadata:**
    Before publishing, ensure all the information in `pyproject.toml` (like `name`, `version`, `description`, `authors`) is correct.

3.  **Build the Package:**
    This command will package your project into a source archive (`.tar.gz`) and a wheel (`.whl`) file, placing them in a `dist/` directory.
    ```bash
    poetry build
    ```

4.  **Publish to PyPI:**
    This command will upload the contents of your `dist/` directory to PyPI.
    ```bash
    poetry publish
    ```
    If this is the first time you are publishing this package, it will be created on PyPI. If the version number in `pyproject.toml` already exists on PyPI, the command will fail.

### Publishing New Versions

To publish an update, you must first update the version number in your `pyproject.toml` file. You can do this manually or use Poetry's `version` command:

```bash
# Examples of updating the version
poetry version patch   # 0.1.0 -> 0.1.1
poetry version minor   # 0.1.0 -> 0.2.0
poetry version major   # 0.1.0 -> 1.0.0
```

After updating the version, simply run the `build` and `publish` commands again:

```bash
poetry build
poetry publish
```
