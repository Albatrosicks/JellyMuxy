package process

import (
	"fmt"
	"os"
	"os/exec"
)

func (p *Processor) MuxFile(videoPath string, tracks []Track) error {
	args := []string{
		"-o", videoPath + ".new",
		videoPath,
	}

	for _, track := range tracks {
		args = append(args, "--language", "0:"+track.Language)
		if track.Name != "" {
			args = append(args, "--track-name", "0:"+track.Name)
		}
		args = append(args, track.Path)
	}

	cmd := exec.Command("mkvmerge", args...)
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("mkvmerge failed: %v", err)
	}

	return os.Rename(videoPath+".new", videoPath)
}
