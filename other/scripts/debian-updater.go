package main

// make sure to build binary first
import (
	"fmt"
	"log"
	"os/exec"
)

func main() {
	commands := [][]string{
		{"sudo", "flatpak", "update", "-y"},
		{"sudo", "apt-get", "update", "-y"},
		{"sudo", "apt-get", "upgrade", "-y"},
		{"sudo", "snap", "refresh"},
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
