/**
 * JiraMaster Loading Overlay — SSE-powered operation feedback.
 *
 * Usage:
 *   startOperation(startUrl, formData, description, {
 *     csrfToken: '...',
 *     eventsUrl: '/tools/events/',  // base URL, op_id appended
 *     onComplete: function(data) { location.reload(); }
 *   });
 */
function startOperation(startUrl, formData, description, options) {
  options = options || {};
  var csrfToken = options.csrfToken || '';
  var eventsBaseUrl = options.eventsUrl || '';
  var onComplete = options.onComplete || function() { location.reload(); };

  // Build overlay DOM
  var overlay = document.createElement('div');
  overlay.className = 'jm-overlay';
  overlay.innerHTML =
    '<div class="card jm-overlay-card shadow-lg">' +
      '<div class="card-body">' +
        '<h5 class="card-title mb-3" id="jm-overlay-title">' + escapeHtml(description) + '</h5>' +
        '<div class="progress mb-3" style="height:6px">' +
          '<div id="jm-overlay-progress" class="progress-bar progress-bar-striped progress-bar-animated" style="width:100%"></div>' +
        '</div>' +
        '<div class="small text-muted mb-2">API Activity</div>' +
        '<div id="jm-overlay-log" class="jm-overlay-log"></div>' +
        '<div id="jm-overlay-summary" class="mt-3 fw-semibold" style="display:none"></div>' +
        '<div class="mt-3 text-end">' +
          '<button id="jm-overlay-close" class="btn btn-sm btn-outline-secondary" style="display:none">Close</button>' +
        '</div>' +
      '</div>' +
    '</div>';
  document.body.appendChild(overlay);

  var logEl = document.getElementById('jm-overlay-log');
  var titleEl = document.getElementById('jm-overlay-title');
  var progressEl = document.getElementById('jm-overlay-progress');
  var summaryEl = document.getElementById('jm-overlay-summary');
  var closeBtn = document.getElementById('jm-overlay-close');

  closeBtn.addEventListener('click', function() {
    overlay.remove();
  });

  function appendLog(html) {
    logEl.innerHTML += html + '\n';
    logEl.scrollTop = logEl.scrollHeight;
  }

  function escapeHtml(text) {
    var d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
  }

  function formatApiCall(evt) {
    var method = evt.method || 'GET';
    var url = evt.url || '';
    // Shorten URL for display: remove scheme + host, keep path
    var displayUrl = url.replace(/^https?:\/\/[^\/]+/, '');
    var params = '';
    if (evt.params) {
      var parts = [];
      for (var k in evt.params) {
        if (evt.params.hasOwnProperty(k)) parts.push(k + '=' + evt.params[k]);
      }
      if (parts.length) params = '?' + parts.join('&');
    }
    return '<span class="api-method">' + method + '</span> <span class="api-url">' + escapeHtml(displayUrl + params) + '</span>';
  }

  function formatApiResponse(evt) {
    var statusClass = (evt.status >= 200 && evt.status < 300) ? 'api-status-ok' : 'api-status-err';
    var text = '<span class="' + statusClass + '">' + evt.status + '</span>';
    if (evt.summary) text += ' <span class="api-summary">' + escapeHtml(evt.summary) + '</span>';
    return '  \u2190 ' + text;
  }

  // Step 1: POST to start the operation
  var fetchOptions = {
    method: 'POST',
    headers: { 'X-CSRFToken': csrfToken },
    body: formData
  };
  fetch(startUrl, fetchOptions)
    .then(function(resp) {
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      return resp.json();
    })
    .then(function(data) {
      if (data.error) throw new Error(data.error);
      var opId = data.operation_id;
      // Step 2: open SSE stream
      var eventSource = new EventSource(eventsBaseUrl + opId);
      eventSource.onmessage = function(e) {
        var evt;
        try { evt = JSON.parse(e.data); } catch(ex) { return; }

        if (evt.type === 'api_call') {
          appendLog(formatApiCall(evt));
        } else if (evt.type === 'api_response') {
          appendLog(formatApiResponse(evt));
        } else if (evt.type === 'status') {
          titleEl.textContent = evt.message || description;
        } else if (evt.type === 'complete') {
          eventSource.close();
          progressEl.classList.remove('progress-bar-striped', 'progress-bar-animated');
          progressEl.classList.add('bg-success');
          if (evt.summary) {
            summaryEl.textContent = evt.summary;
            summaryEl.className = 'mt-3 fw-semibold text-success';
            summaryEl.style.display = '';
          }
          titleEl.textContent = evt.message || 'Complete';
          closeBtn.style.display = '';
          closeBtn.textContent = 'Close & Refresh';
          closeBtn.className = 'btn btn-sm btn-primary';
          closeBtn.onclick = function() { overlay.remove(); onComplete(evt); };
        } else if (evt.type === 'error') {
          eventSource.close();
          progressEl.classList.remove('progress-bar-striped', 'progress-bar-animated');
          progressEl.classList.add('bg-danger');
          summaryEl.textContent = evt.message || 'Operation failed';
          summaryEl.className = 'mt-3 fw-semibold text-danger';
          summaryEl.style.display = '';
          titleEl.textContent = 'Error';
          closeBtn.style.display = '';
        }
        // keepalive — ignored
      };
      eventSource.onerror = function() {
        eventSource.close();
        progressEl.classList.remove('progress-bar-striped', 'progress-bar-animated');
        progressEl.classList.add('bg-danger');
        summaryEl.textContent = 'Connection to server lost';
        summaryEl.className = 'mt-3 fw-semibold text-danger';
        summaryEl.style.display = '';
        closeBtn.style.display = '';
      };
    })
    .catch(function(err) {
      progressEl.classList.remove('progress-bar-striped', 'progress-bar-animated');
      progressEl.classList.add('bg-danger');
      summaryEl.textContent = err.message || 'Failed to start operation';
      summaryEl.className = 'mt-3 fw-semibold text-danger';
      summaryEl.style.display = '';
      closeBtn.style.display = '';
    });
}
