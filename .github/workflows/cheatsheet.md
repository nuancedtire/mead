### Controlling How Often the Workflow Runs

To control how often your GitHub Actions workflow fetches the data, you can modify the `cron` schedule in your `.yml` file. The `cron` syntax is flexible and allows you to set the frequency of the workflow execution.

Here’s a quick guide:

### 1. **Cron Syntax**
The cron syntax in GitHub Actions follows this structure:

```plaintext
* * * * *
| | | | |
| | | | +---- Day of the week (0 - 7) (Sunday is 0 or 7)
| | | +------ Month (1 - 12)
| | +-------- Day of the month (1 - 31)
| +---------- Hour (0 - 23)
+------------ Minute (0 - 59)
```

#### Examples:
- **Every Day at Midnight**:
  ```yaml
  cron: '0 0 * * *'
  ```
- **Every Hour**:
  ```yaml
  cron: '0 * * * *'
  ```
- **Every Monday at 9 AM**:
  ```yaml
  cron: '0 9 * * 1'
  ```
- **Every 15 Minutes**:
  ```yaml
  cron: '*/15 * * * *'
  ```

### 2. **Adding a Cheatsheet to the Repository**

You can create a `README.md` file or a `CHEATSHEET.md` in your repository to store important notes, including how to control the workflow frequency and other configurations.

#### Example of `CHEATSHEET.md`:

```markdown
# GitHub Actions Cheatsheet

## Controlling Workflow Frequency

The fetch frequency is controlled using the `cron` syntax in the GitHub Actions workflow file (`.github/workflows/update_csv.yml`).

### Cron Examples:

- **Every Day at Midnight**: 
  ```yaml
  cron: '0 0 * * *'
  ```
- **Every Hour**:
  ```yaml
  cron: '0 * * * *'
  ```
- **Every Monday at 9 AM**:
  ```yaml
  cron: '0 9 * * 1'
  ```
- **Every 15 Minutes**:
  ```yaml
  cron: '*/15 * * * *'
  ```

### Updating the Cron Schedule
1. Open the `update_csv.yml` file located in `.github/workflows/`.
2. Modify the `cron` expression under the `schedule` key.
3. Commit and push the changes.

## Additional Configurations

### Logging Levels

- **INFO**: Standard logging, useful for tracking general script execution.
- **WARNING**: Logs potential issues that don’t stop the script but could be concerning.
- **ERROR**: Logs critical issues that prevent the script from continuing.

### Python Dependencies

- **requests**: For making HTTP requests.
- **pandas**: For handling data structures and CSV files.

### GitHub Actions Permissions

Ensure the repository’s action permissions are set to "Read and write permissions" under the repository settings for GitHub Actions.

### Manual Triggering

To manually trigger the workflow:
1. Go to the "Actions" tab in your GitHub repository.
2. Select the workflow named "Update CSV Daily".
3. Click "Run workflow".

### Useful Links
- [GitHub Actions Cron Syntax](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#scheduled-events)
- [GitHub Actions Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
