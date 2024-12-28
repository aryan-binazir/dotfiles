package main

// make sure to build binary first
import (
	"fmt"
	"log"
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
		output, err := cmd.CombinedOutput()
		if err != nil {
			log.Fatal(err)
		}
		fmt.Printf("%s\n", output)
	}
}
