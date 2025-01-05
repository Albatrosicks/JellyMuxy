package db

import (
	"database/sql"
	"time"

	_ "github.com/mattn/go-sqlite3"
)

type FileStatus string

const (
	StatusWaiting    FileStatus = "waiting"
	StatusProcessing FileStatus = "processing"
	StatusProcessed  FileStatus = "processed"
	StatusError      FileStatus = "error"
)

type FileRecord struct {
	ID          int64
	Path        string
	ModHash     string
	Status      FileStatus
	StatusMsg   string
	IsH265      bool
	LastChecked time.Time
}

func InitDB(dbPath string) (*sql.DB, error) {
	db, err := sql.Open("sqlite3", dbPath)
	if err != nil {
		return nil, err
	}

	_, err = db.Exec(`
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            path TEXT UNIQUE,
            mod_hash TEXT,
            status TEXT,
            status_msg TEXT,
            is_h265 BOOLEAN,
            last_checked TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_path ON files(path);
        CREATE INDEX IF NOT EXISTS idx_status ON files(status);
    `)
	return db, err
}
