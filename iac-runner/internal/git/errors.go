package git

// Error is the typed git failure every exported Manager method
// returns.
type Error struct {
	Code    string
	Message string
	Hint    string
	wrapped error
}

func (e *Error) Error() string { return "" }

func (e *Error) Unwrap() error { return e.wrapped }

// Classify maps a git stderr blob onto the git_* taxonomy.
func Classify(stderr string, exitCode int, fallback string) (string, string) {
	return "", ""
}
