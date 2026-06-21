package main

import (
	"bytes"
	"errors"
	"os"
	"os/exec"
)

var agentCommands = map[string][]string{
	"acc": {"claude", "--dangerously-skip-permissions"},
	"acd": {"codex", "--yolo"},
	"acu": {"cursor-agent", "--force"},
}

func main() {
	os.Exit(run(os.Args[1:]))
}

func run(args []string) int {
	branch, commands := parseArgs(args)

	if status := runCommand("git", "fetch"); status != 0 {
		return status
	}

	worktreeStatus, status := statusPorcelain()
	if status != 0 {
		return status
	}

	if worktreeStatus != "" {
		status := runCommand(
			"git",
			"stash",
			"push",
			"--include-untracked",
			"-m",
			"gb auto-stash before checkout "+branch,
		)
		if status != 0 {
			return status
		}
	}

	for _, argv := range [][]string{
		{"git", "checkout", branch},
		{"git", "pull"},
	} {
		if status := runCommand(argv[0], argv[1:]...); status != 0 {
			return status
		}
	}

	for _, command := range commands {
		if argv, ok := agentCommands[command]; ok {
			if status := runCommand(argv[0], argv[1:]...); status != 0 {
				return status
			}
			continue
		}

		if status := runCommand("zsh", "-ic", command); status != 0 {
			return status
		}
	}

	return 0
}

func parseArgs(args []string) (string, []string) {
	if len(args) == 0 {
		return "main", nil
	}

	if _, ok := agentCommands[args[0]]; ok {
		return "main", args
	}

	return args[0], args[1:]
}

func statusPorcelain() (string, int) {
	var stdout bytes.Buffer
	cmd := exec.Command("git", "status", "--porcelain")
	cmd.Stdin = os.Stdin
	cmd.Stdout = &stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		return "", exitCode(err)
	}

	return stdout.String(), 0
}

func runCommand(name string, args ...string) int {
	cmd := exec.Command(name, args...)
	cmd.Stdin = os.Stdin
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr

	if err := cmd.Run(); err != nil {
		return exitCode(err)
	}

	return 0
}

func exitCode(err error) int {
	var exitErr *exec.ExitError
	if errors.As(err, &exitErr) {
		return exitErr.ExitCode()
	}

	return 1
}
