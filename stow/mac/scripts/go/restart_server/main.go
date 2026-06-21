package main

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
)

func main() {
	os.Exit(run(os.Args[1:]))
}

func run(args []string) int {
	if !validArgs(args) {
		fmt.Fprintln(os.Stderr, usage())
		return 2
	}

	dev := len(args) == 1 && args[0] == "dev"
	reposDir := reposDir()
	tsRepo := filepath.Join(reposDir, "bball-lab-ts")
	goRepo := filepath.Join(reposDir, "bball-lab-go")

	requiredCommands := []string{"gb", "make"}
	if dev {
		requiredCommands = []string{"make"}
	}

	for _, command := range requiredCommands {
		if status := requireCommand(command); status != 0 {
			return status
		}
	}

	requiredDirs := []string{tsRepo, goRepo}
	if dev {
		requiredDirs = []string{goRepo}
	}

	for _, repo := range requiredDirs {
		if status := requireDir(repo); status != 0 {
			return status
		}
	}

	if !dev {
		if status := runRepoPulls([]string{tsRepo, goRepo}); status != 0 {
			return status
		}
	}

	if status := runInRepo(goRepo, "make", "down"); status != 0 {
		return status
	}

	return runInRepo(goRepo, "make", "up")
}

func runRepoPulls(repos []string) int {
	var wg sync.WaitGroup
	statuses := make([]int, len(repos))

	for i, repo := range repos {
		wg.Add(1)
		go func(i int, repo string) {
			defer wg.Done()
			statuses[i] = runInRepo(repo, "gb")
		}(i, repo)
	}

	wg.Wait()

	for _, status := range statuses {
		if status != 0 {
			return status
		}
	}

	return 0
}

func usage() string {
	return "usage: restart_server [dev]"
}

func validArgs(args []string) bool {
	return len(args) == 0 || (len(args) == 1 && args[0] == "dev")
}

func reposDir() string {
	if value, ok := os.LookupEnv("REPOS_DIR"); ok {
		return expandUser(value)
	}

	home, err := os.UserHomeDir()
	if err != nil {
		return filepath.Join("~", "repos")
	}

	return filepath.Join(home, "repos")
}

func expandUser(path string) string {
	if path == "~" {
		home, err := os.UserHomeDir()
		if err == nil {
			return home
		}
	}

	if strings.HasPrefix(path, "~/") {
		home, err := os.UserHomeDir()
		if err == nil {
			return filepath.Join(home, path[2:])
		}
	}

	return path
}

func requireCommand(name string) int {
	if _, err := exec.LookPath(name); err != nil {
		fmt.Fprintf(os.Stderr, "Missing required command: %s\n", name)
		return 1
	}

	return 0
}

func requireDir(path string) int {
	info, err := os.Stat(path)
	if err != nil || !info.IsDir() {
		fmt.Fprintf(os.Stderr, "Missing repo directory: %s\n", path)
		return 1
	}

	return 0
}

func runInRepo(repo string, name string, args ...string) int {
	fmt.Printf("\n==> %s\n", repo)

	cmd := exec.Command(name, args...)
	cmd.Dir = repo
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
