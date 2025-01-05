package web

import (
	"database/sql"
	"html/template"
	"net/http"
	"path/filepath"
	"strings"
)

type FileRecord struct {
	Path        string
	Status      string
	StatusMsg   string
	DisplayPath string
}

type Server struct {
	db   *sql.DB
	tmpl *template.Template
	mux  *http.ServeMux
}

func NewServer(db *sql.DB) *Server {
	tmpl := template.Must(template.ParseFiles(
		"internal/web/templates/layout.html",
		"internal/web/templates/content.html",
	))

	s := &Server{
		db:   db,
		tmpl: tmpl,
		mux:  http.NewServeMux(),
	}

	s.mux.HandleFunc("/", s.handleRoot)
	s.mux.HandleFunc("/content", s.handleContent)

	return s
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.mux.ServeHTTP(w, r)
}

func (s *Server) getFilesByCategory() (map[string][]FileRecord, error) {
	rows, err := s.db.Query(`
       SELECT path, status, status_msg
       FROM files
       ORDER BY path
   `)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	filesByCategory := make(map[string][]FileRecord)
	for rows.Next() {
		var f FileRecord
		var statusMsg sql.NullString
		if err := rows.Scan(&f.Path, &f.Status, &statusMsg); err != nil {
			return nil, err
		}

		if statusMsg.Valid {
			f.StatusMsg = statusMsg.String
		}
		f.DisplayPath = filepath.Base(f.Path)
		category := getCategoryFromPath(f.Path)
		filesByCategory[category] = append(filesByCategory[category], f)
	}

	return filesByCategory, nil
}

func (s *Server) handleRoot(w http.ResponseWriter, r *http.Request) {
	files, err := s.getFilesByCategory()
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}

	data := struct {
		FilesByCategory map[string][]FileRecord
	}{
		FilesByCategory: files,
	}

	s.tmpl.ExecuteTemplate(w, "layout.html", data)
}

func (s *Server) handleContent(w http.ResponseWriter, r *http.Request) {
	files, err := s.getFilesByCategory()
	if err != nil {
		http.Error(w, err.Error(), 500)
		return
	}

	data := struct {
		FilesByCategory map[string][]FileRecord
	}{
		FilesByCategory: files,
	}

	s.tmpl.ExecuteTemplate(w, "content", data)
}

func getCategoryFromPath(path string) string {
	parts := strings.Split(path, string(filepath.Separator))
	for _, part := range parts {
		lower := strings.ToLower(part)
		if strings.Contains(lower, "series") || strings.Contains(lower, "movies") {
			return part
		}
	}
	return "Other"
}
