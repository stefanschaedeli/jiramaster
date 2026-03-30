// JiraMaster frontend utilities

/**
 * Copy the contents of a textarea/input to the clipboard.
 * @param {string} elementId - ID of the element to copy from
 */
function copyToClipboard(elementId) {
  const el = document.getElementById(elementId);
  if (!el) return;

  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(el.value).then(() => {
      showCopyFeedback(elementId);
    }).catch(() => {
      fallbackCopy(el);
    });
  } else {
    fallbackCopy(el);
  }
}

function fallbackCopy(el) {
  el.select();
  el.setSelectionRange(0, 99999);
  try {
    document.execCommand('copy');
    showCopyFeedback(el.id);
  } catch (e) {
    console.warn('Copy failed', e);
  }
}

function showCopyFeedback(elementId) {
  const btn = document.querySelector(`button[onclick="copyToClipboard('${elementId}')"]`);
  if (!btn) return;
  const original = btn.textContent;
  btn.textContent = 'Copied!';
  btn.classList.add('btn-success');
  btn.classList.remove('btn-outline-secondary');
  setTimeout(() => {
    btn.textContent = original;
    btn.classList.remove('btn-success');
    btn.classList.add('btn-outline-secondary');
  }, 2000);
}

// ── Import view: toggle story list visibility ────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {
  // Story toggle buttons
  document.querySelectorAll('.story-toggle-btn').forEach(function (btn) {
    const targetId = btn.getAttribute('data-stories');
    const target = document.getElementById(targetId);
    if (!target) return;

    // Start collapsed
    target.style.display = 'none';
    btn.setAttribute('data-expanded', 'false');

    btn.addEventListener('click', function () {
      const expanded = btn.getAttribute('data-expanded') === 'true';
      if (expanded) {
        target.style.display = 'none';
        btn.setAttribute('data-expanded', 'false');
        btn.textContent = btn.textContent.replace('▴', '▾');
      } else {
        target.style.display = 'block';
        btn.setAttribute('data-expanded', 'true');
        btn.textContent = btn.textContent.replace('▾', '▴');
      }
    });
  });

  // Epic checkbox: disable all story checkboxes when epic unchecked
  document.querySelectorAll('.epic-toggle').forEach(function (epicCb) {
    epicCb.addEventListener('change', function () {
      const idx = this.getAttribute('data-epic-index');
      const storyCbs = document.querySelectorAll(`input[name^="story_${idx}_"]`);
      storyCbs.forEach(function (cb) {
        cb.disabled = !epicCb.checked;
        if (!epicCb.checked) cb.checked = false;
      });
    });
  });
});
