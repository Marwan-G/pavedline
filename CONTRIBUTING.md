# Contributing to Pavedline

Thanks for your interest. Pavedline is a Claude Code plugin marketplace; contributions are welcome.

## Ground rules

- Python code uses the standard library only and targets Python 3.10+.
- Run the tests with `python3 -m unittest discover -s tests -t .`.
- Validate manifests with `claude plugin validate . --strict` and
  `claude plugin validate plugins/pavedline --strict`.
- Keep changes focused: one concern per pull request, with tests for new behavior.
- Do not commit secrets, local paths, or identifiers that belong to a private project.

## Workflow

1. Fork the repository and create a branch.
2. Write a failing test, make it pass, and keep the suite green.
3. Open a pull request describing the change and why it is needed.

## License

By contributing you agree that your contributions are licensed under the MIT License.
