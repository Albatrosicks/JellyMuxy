package process

import (
	"encoding/json"
	"os/exec"
)

func IsH265(filepath string) (bool, error) {
	cmd := exec.Command("ffprobe",
		"-v", "quiet",
		"-print_format", "json",
		"-show_streams",
		filepath)

	output, err := cmd.Output()
	if err != nil {
		return false, err
	}

	var data struct {
		Streams []struct {
			CodecName string `json:"codec_name"`
		} `json:"streams"`
	}

	if err := json.Unmarshal(output, &data); err != nil {
		return false, err
	}

	for _, stream := range data.Streams {
		if stream.CodecName == "hevc" {
			return true, nil
		}
	}
	return false, nil
}
