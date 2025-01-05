package process

import (
	"database/sql"
)

type Processor struct {
	db               *sql.DB
	MaxFuzzyDistance int
}

func NewProcessor(db *sql.DB) *Processor {
	return &Processor{
		db:               db,
		MaxFuzzyDistance: 3, // Default fuzzy match threshold
	}
}

func (p *Processor) ProcessNextFile() error {
	// TODO: Implement file processing logic
	return nil
}
