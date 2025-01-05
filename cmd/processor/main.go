package main

import (
	"log"
	"net/http"
	"time"

	"github.com/Albatrosicks/JellyMuxy/internal/db"
	"github.com/Albatrosicks/JellyMuxy/internal/process"
	"github.com/Albatrosicks/JellyMuxy/internal/scan"
	"github.com/Albatrosicks/JellyMuxy/internal/web"
)

func main() {
	database, err := db.InitDB("/config/media.db")
	if err != nil {
		log.Fatal(err)
	}
	defer database.Close()

	scanner := scan.NewScanner(database)
	processor := process.NewProcessor(database)
	server := web.NewServer(database)

	go func() {
		for {
			if err := scanner.ScanDirectory("/data"); err != nil {
				log.Printf("Scan error: %v", err)
			}
			time.Sleep(5 * time.Minute)
		}
	}()

	go func() {
		for {
			if err := processor.ProcessNextFile(); err != nil {
				log.Printf("Process error: %v", err)
			}
			time.Sleep(1 * time.Second)
		}
	}()

	log.Fatal(http.ListenAndServe(":8080", server))
}
