package scan

import (
	"crypto/sha1"
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/Albatrosicks/JellyMuxy/internal/process"
)

type FileRecord struct {
	Path        string
	ModHash     string
	Status      FileStatus
	StatusMsg   string
	LastChecked time.Time
}

type FileStatus string

const (
	StatusWaiting    FileStatus = "waiting"
	StatusProcessing FileStatus = "processing"
	StatusProcessed  FileStatus = "processed"
	StatusError      FileStatus = "error"
)

type Scanner struct {
	db        *sql.DB
	processor *process.Processor
}

func NewScanner(db *sql.DB) *Scanner {
	return &Scanner{
		db:        db,
		processor: process.NewProcessor(db),
	}
}

func (s *Scanner) GenerateModHash(info os.FileInfo) string {
	data := fmt.Sprintf("%d-%d", info.ModTime().UnixNano(), info.Size())
	hash := sha1.Sum([]byte(data))
	return fmt.Sprintf("%x", hash)
}

func (s *Scanner) ScanDirectory(root string) error {
	return filepath.Walk(root, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		if !info.IsDir() && strings.HasSuffix(strings.ToLower(path), ".mkv") {
			modHash := s.GenerateModHash(info)

			// Check if file exists and hash changed
			var existing FileRecord
			err := s.db.QueryRow("SELECT mod_hash FROM files WHERE path = ?", path).Scan(&existing.ModHash)

			if err == sql.ErrNoRows || existing.ModHash != modHash {
				// New or modified file - queue for processing
				_, err = s.db.Exec(`
                    INSERT INTO files (path, mod_hash, status, last_checked)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(path) DO UPDATE SET
                        mod_hash=excluded.mod_hash,
                        status=?,
                        last_checked=excluded.last_checked
                `, path, modHash, StatusWaiting, time.Now(), StatusWaiting)
			}
		}
		return nil
	})
}
