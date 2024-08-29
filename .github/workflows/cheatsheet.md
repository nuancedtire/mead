### Controlling How Often the Workflow Runs

To control how often your GitHub Actions workflow fetches the data, you can modify the `cron` schedule in your `.yml` file. The `cron` syntax is flexible and allows you to set the frequency of the workflow execution.

Here’s a quick guide:

### **Cron Syntax**
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

### Updating the Cron Schedule
1. Open the `update_csv.yml` file located in `.github/workflows/`.
2. Modify the `cron` expression under the `schedule` key.
3. Commit and push the changes.

## Additional Configurations

### Manual Triggering

To manually trigger the workflow:
1. Go to the "Actions" tab in your GitHub repository.
2. Select the workflow named "Update CSV Daily".
3. Click "Run workflow".

### Useful Links
- [GitHub Actions Cron Syntax](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#scheduled-events)
- [GitHub Actions Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)
