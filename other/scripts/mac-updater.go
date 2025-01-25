package main

// make sure to build binary first
import (
	"os"
	"os/exec"
)

func main() {
	commands := [][]string{
		{"brew", "update"},
		{"brew", "upgrade"},
		{"brew", "upgrade", "--cask", "--greedy"},
	}

	for _, command := range commands {
		cmd := exec.Command(command[0], command[1:]...)
		cmd.Stdout = os.Stderr
		cmd.Stderr = os.Stderr
		
		if err := cmd.Run(); err != nil {
			os.Exit(1)
		}
	}
}
