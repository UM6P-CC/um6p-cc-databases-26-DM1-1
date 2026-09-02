# Data Management Labs 

## 1. Getting started with a lab

1. **Accept the assignment** using the link/command your instructor shares.
2. **Clone your repository** to your own computer.
3. **One-time setup** — before your first submission, open `.github/workflows/autograde.yaml` in your repo and add this line:
   ```yaml
   jobs:
     grade:
       uses: "UM6P-CC/classroom50/.github/workflows/autograde-runner.yaml@main"
       secrets: inherit
   ```
4. **Write your answers** in the location specified for that lab (see below).
5. Save your work then run:
   ```
   gh student submit
   ```
6. Check the **Actions** tab of your repo to see your grading results.


## 2. Where to write your answers

- **Most labs:** open `tests/test_labN.py` (e.g. `test_lab0.py`, `test_lab3.py`) and fill in each blank:
  ```python
  sql = """
  -- WRITE YOUR SQL HERE
  """
  ```
  Write your SQL directly inside the triple quotes. Do not rename, delete, or restructure the surrounding test code ,only edit the SQL inside each block.
  

## 3. Waiting for your repository to go public

When you accept an assignment, your repository starts out private. A background process runs periodically and flips eligible lab repositories to public, this is required for grading to work correctly. This usually happens within about 15 minutes of accepting.

Do not push your solution or run `gh student submit` until your repository shows as Public .


## 4. Starting from Lab 3: how grading works

From Lab 3 onward, each lab includes a schema and a populated dataset that your queries run against:
- **Lab 3** → `seed.sql`
- **Lab 4** → `lab4_seed.sql`
- **Lab 5** → `lab5_seed.sql`

These files are already in your repo, you can look at the data directly to understand what you're querying.
**Important:** Your SQL is also tested using a hidden dataset. Therefore, write general SQL queries that solve the question. Do not write queries that only match the specific values in the visible dataset.


## 5. Submitting

```
gh student submit
```

You can submit multiple times — each submission is graded independently, and your most recent submission is what counts. Check the **Actions** tab after each submission to see your score and any failure details.

