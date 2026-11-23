package worker

import (
	"context"
	"fmt"
)

type JobQueue interface {
	Push(ctx context.Context, job string) error
	Pop(ctx context.Context) (string, error)
}

type WorkerService struct {
	Queue JobQueue
}

func NewWorkerService(q JobQueue) *WorkerService {
	return &WorkerService{Queue: q}
}

func (w *WorkerService) ProcessJobs(ctx context.Context) error {
	job, err := w.Queue.Pop(ctx)
	if err != nil {
		return err
	}
	fmt.Println("Processing job:", job)
	return nil
}
