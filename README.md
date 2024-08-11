# GitHub Issues Duplicate Detector 🔍 | AI-powered 🧠

<kbd>ghidd</kbd> (pronounced `[ɡɪd]`, standing as the acronym of the above) is an action exploiting latest [NLP](https://en.wikipedia.org/wiki/Natural_language_processing) platform [gpt-4o-mini](https://platform.openai.com/docs/models/gpt-4o-mini) from OpenAI to understand GitHub issue's context and contents for detecting if could be a duplicate of any already existing issue(s) in your repository.

---
## ❗Pre-requisites
You shall already have signed up for an OpenAI account and have generated a valid [API key](https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key).

## ⚠️ Notes
It's recommended to set API spending limit in your OpenAI API profile to clamp associated costs.
API calls in the code are already fairly optimized to minimize both input and output tokens, driving overall [cost](https://openai.com/api/pricing/):
- context (input) tokens by accurate prompting and trimming excessively verbose issue text bodies
- generated (output) tokens by accurate role playing and reasoning guidance leading to telegram-style response

## 📓 How to use it
<kbd>ghidd</kbd> requires you to set up a few items first:
1. Go to your repository `settings` > `secrets and variables` > `actions` and create `new repository secret` called `OPENAI_API_KEY` (_case sensitive, do not name differently_) with your user's API key as its secret value. Save it.
2. Create workflow `.yml` file in your repository to trigger action execution. Boilerplate below can be used as example:
```yaml
name: Check duplicate issues in repository

on:
  issues:
    types:
      - opened

permissions:
  contents: read
  issues: write
  pull-requests: write

jobs:
  check-duplicate-repo-issues:
    runs-on: ubuntu-latest
    steps:
      - name: Run public action
        uses: 01x4-dev/ghidd@v0
        id: run-action
        with:
          mode: 'new'
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          PAT: ${{ secrets.GITHUB_TOKEN }}
          OWNER_REPO: ${{ github.repository }}

      - name: Handle output for optional use
        id: use-output
        run: echo ${{ steps.run-action.outputs.duplicates-found }} duplicates found
```
4. Set action's inputs under the `with:` workflow clause to best fit your needs:

| Inputs | Description | Default Value |
| :--- | :--- | :--- |
| mode | Operating mode. `all` or `new` respectively for cross checking for duplicates all existing issues or just the newly created issue. The first is recommended to make a first pass through all existing open issues and spot any candidate duplicate. Then you can switch to the latter mode to focus only on newly created issues from there on.  | `all` |
| duplCmtH | Header to identify bot comment of duplicate issue found | `> [!WARNING]\n> :robot: **_duplicate issue detected_** :robot:` |
| duplLabel | Repo label to tag duplicate issues with, described as JSON string following GitHub API specs | `{ "name": "duplicate", "description": "This issue or pull request already exists", "color": "d93f0b" }` |

✨ Upon creating a new issue, action will be triggered to run automatically.

✔️ If duplicate issue is identified, a notification comment is added to them accordingly.

---
<details>
<summary> How to use privately (i.e. local fork) </summary>
If desired, you can run the action locally upon changing your workflow file following the example below.

```yaml
name: Check duplicate repo issues in repository

on:
  issues:
    types:
      - opened

permissions:
  contents: read
  issues: write
  pull-requests: write

jobs:
  check-duplicate-repo-issues:
    runs-on: ubuntu-latest
    steps:
      # To use this repository's private action you must check out the repository
      - name: Checkout repo contents
        id: checkout-repo
        if: ${{ always() }}
        uses: actions/checkout@v4

      - name: Run action in root directory
        uses: ./
        id: run-action
        with:
          mode: 'new'
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          PAT: ${{ secrets.GITHUB_TOKEN }}
          OWNER_REPO: ${{ github.repository }}

      - name: Handle output for optional use
        id: use-output
        run: echo ${{ steps.run-action.outputs.duplicates-found }} duplicates found
```
</details>
