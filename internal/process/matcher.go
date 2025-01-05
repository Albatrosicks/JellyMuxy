package process

import (
	"fmt"
	"path/filepath"
	"strings"

	"github.com/lithammer/fuzzysearch/fuzzy"
)

type Track struct {
	Path     string
	Language string
	Name     string
	Type     string // subtitle or audio
}

func (p *Processor) MatchTracks(videoPath string, tracks []Track) ([]Track, error) {
	videoBase := strings.TrimSuffix(filepath.Base(videoPath), filepath.Ext(videoPath))
	matched := make([]Track, 0)

	// Group tracks by type and language
	typeMatches := make(map[string][]Track)
	for _, track := range tracks {
		key := track.Type + "-" + track.Language
		typeMatches[key] = append(typeMatches[key], track)
	}

	// For each group, find best match
	for _, group := range typeMatches {
		bestDist := -1
		var bestTrack *Track
		hasTie := false

		for _, track := range group {
			trackBase := strings.TrimSuffix(filepath.Base(track.Path), filepath.Ext(track.Path))
			dist := fuzzy.LevenshteinDistance(videoBase, trackBase)

			if bestDist == -1 || dist < bestDist {
				bestDist = dist
				bestTrack = &track
				hasTie = false
			} else if dist == bestDist {
				hasTie = true
			}
		}

		if hasTie {
			return nil, fmt.Errorf("tie in fuzzy matching for %s tracks", group[0].Type)
		}

		if bestTrack != nil && bestDist <= p.MaxFuzzyDistance {
			matched = append(matched, *bestTrack)
		}
	}

	return matched, nil
}
