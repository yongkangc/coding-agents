package main

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"os"
	"os/exec"
	"strings"

	"github.com/anthropics/anthropic-sdk-go"
	"github.com/joho/godotenv"
)

func main() {
	// Load .env file if present
	_ = godotenv.Load()

	client := anthropic.NewClient()

	scanner := bufio.NewScanner(os.Stdin)
	getUserMessage := func() (string, bool) {
		if !scanner.Scan() {
			return "", false
		}
		return scanner.Text(), true
	}

	agent := NewAgent(&client, getUserMessage)
	err := agent.Run(context.TODO())
	if err != nil {
		fmt.Printf("Error: %s\n", err.Error())
	}
}

func NewAgent(client *anthropic.Client, getUserMessage func() (string, bool)) *Agent {
	return &Agent{
		client:         client,
		getUserMessage: getUserMessage,
	}
}

type Agent struct {
	client         *anthropic.Client
	getUserMessage func() (string, bool)
}

func (a *Agent) Run(ctx context.Context) error {
	conversation := []anthropic.MessageParam{}

	fmt.Println("Chat with Claude (use 'ctrl-c' to quit)")

	for {
		fmt.Print("\u001b[94mYou\u001b[0m: ")
		userInput, ok := a.getUserMessage()
		if !ok {
			break
		}

		userMessage := anthropic.NewUserMessage(anthropic.NewTextBlock(userInput))
		conversation = append(conversation, userMessage)

		message, err := a.runInference(ctx, conversation)
		if err != nil {
			return err
		}
		conversation = append(conversation, message.ToParam())

		// Check for tool call in Claude's response
		toolHandled := false
		for _, content := range message.Content {
			if content.Type == "text" && strings.HasPrefix(content.Text, "tool:") {
				result := a.handleToolCall(content.Text)
				conversation = append(conversation, anthropic.NewUserMessage(anthropic.NewTextBlock(result)))
				toolHandled = true
				break
			}
		}
		if toolHandled {
			continue // Skip printing, go to next loop iteration
		}

		for _, content := range message.Content {
			switch content.Type {
			case "text":
				fmt.Printf("\u001b[93mClaude\u001b[0m: %s\n", content.Text)
			}
		}
	}

	return nil
}

func (a *Agent) runInference(ctx context.Context, conversation []anthropic.MessageParam) (*anthropic.Message, error) {
	message, err := a.client.Messages.New(ctx, anthropic.MessageNewParams{
		Model:     anthropic.ModelClaude3_7SonnetLatest,
		MaxTokens: int64(1024),
		Messages:  conversation,
	})
	return message, err
}

func (a *Agent) handleToolCall(toolCall string) string {
	// Example: tool: read_file({"path":"foo.js"})
	toolCall = strings.TrimPrefix(toolCall, "tool: ")
	openParen := strings.Index(toolCall, "(")
	closeParen := strings.LastIndex(toolCall, ")")
	if openParen == -1 || closeParen == -1 {
		return "Invalid tool call format."
	}
	toolName := toolCall[:openParen]
	argsJSON := toolCall[openParen+1 : closeParen]

	switch toolName {
	case "read_file":
		var args struct {
			Path string `json:"path"`
		}
		if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
			return "Invalid arguments for read_file."
		}
		return readFileTool(args.Path)
	case "edit_file":
		var args struct {
			Path   string `json:"path"`
			OldStr string `json:"old_str"`
			NewStr string `json:"new_str"`
		}
		if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
			return "Invalid arguments for edit_file."
		}
		return editFileTool(args.Path, args.OldStr, args.NewStr)
	case "run_command":
		var args struct {
			Cmd string `json:"cmd"`
		}
		if err := json.Unmarshal([]byte(argsJSON), &args); err != nil {
			return "Invalid arguments for run_command."
		}
		return runCommandTool(args.Cmd)
	case "list_files":
		return listFilesTool()
	default:
		return "Unknown tool: " + toolName
	}
}

func readFileTool(path string) string {
	data, err := ioutil.ReadFile(path)
	if err != nil {
		return "Error reading file: " + err.Error()
	}
	return string(data)
}

func editFileTool(path, oldStr, newStr string) string {
	data, err := ioutil.ReadFile(path)
	if err != nil {
		return "Error reading file: " + err.Error()
	}
	content := string(data)
	if !strings.Contains(content, oldStr) {
		return "Old string not found in file."
	}
	newContent := strings.Replace(content, oldStr, newStr, 1)
	err = ioutil.WriteFile(path, []byte(newContent), 0644)
	if err != nil {
		return "Error writing file: " + err.Error()
	}
	return "File edited successfully."
}

func runCommandTool(cmdStr string) string {
	cmd := exec.Command("sh", "-c", cmdStr)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return "Command error: " + err.Error() + "\n" + string(output)
	}
	return string(output)
}

func listFilesTool() string {
	files, err := ioutil.ReadDir(".")
	if err != nil {
		return "Error listing files: " + err.Error()
	}
	var names []string
	for _, f := range files {
		if f.IsDir() {
			names = append(names, f.Name()+"/")
		} else {
			names = append(names, f.Name())
		}
	}
	return strings.Join(names, "\n")
}
