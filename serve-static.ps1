$root = 'c:\Users\Jake\OneDrive\Desktop\DAA'
$listener = New-Object System.Net.HttpListener
$prefix = 'http://localhost:8080/'
$listener.Prefixes.Add($prefix)
$listener.Start()
Write-Host "Serving $root at $prefix (Press Ctrl+C to stop)"
while ($listener.IsListening) {
  try {
    $context = $listener.GetContext()
  } catch {
    break
  }
  $req = $context.Request
  $res = $context.Response
  $file = $req.Url.LocalPath.TrimStart('/')
  if ([string]::IsNullOrWhiteSpace($file)) { $file = 'static/index.html' }
  $path = Join-Path $root $file
  if (-not (Test-Path $path) -or (Get-Item $path).PSIsContainer) {
    $res.StatusCode = 404
    $bytes = [System.Text.Encoding]::UTF8.GetBytes('404 Not Found')
    $res.ContentType = 'text/plain'
    $res.OutputStream.Write($bytes,0,$bytes.Length)
    $res.Close()
    continue
  }
  $ext = [IO.Path]::GetExtension($path).ToLower()
  switch ($ext) {
    '.html' { $mime='text/html' }
    '.css'  { $mime='text/css' }
    '.js'   { $mime='application/javascript' }
    '.png'  { $mime='image/png' }
    '.jpg'  { $mime='image/jpeg' }
    '.jpeg' { $mime='image/jpeg' }
    '.svg'  { $mime='image/svg+xml' }
    '.json' { $mime='application/json' }
    default { $mime='application/octet-stream' }
  }
  try {
    $bytes = [System.IO.File]::ReadAllBytes($path)
    $res.ContentType = $mime
    $res.OutputStream.Write($bytes,0,$bytes.Length)
  } catch {
    $res.StatusCode = 500
    $err = [System.Text.Encoding]::UTF8.GetBytes('500 Internal Server Error')
    $res.OutputStream.Write($err,0,$err.Length)
  }
  $res.Close()
}
$listener.Stop()
$listener.Close()
