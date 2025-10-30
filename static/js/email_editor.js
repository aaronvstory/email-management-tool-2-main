/**
 * Enhanced Email Editor Functions
 * Provides full email editing capabilities with rich text support
 */

// Open the email editor with full content
function openEmailEditor(emailId) {
    console.log(`Opening email editor for ID: ${emailId}`);

    // Fetch complete email details
    fetch(`/email/${emailId}/full`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Loaded email data:', data);

            if (data.error) {
                alert(`Error: ${data.error}`);
                return;
            }

            // Populate all fields with actual email content
            document.getElementById('editorEmailId').value = data.id;
            document.getElementById('editorEmailFrom').textContent = data.sender || 'Unknown';
            document.getElementById('editorEmailTo').textContent = data.recipients || 'Unknown';
            document.getElementById('editorEmailSubject').value = data.subject || '';
            document.getElementById('editorEmailBody').value = data.body_text || '';
            document.getElementById('editorEmailBodyHtml').value = data.body_html || '';

            // Set risk information
            document.getElementById('editorRiskScore').textContent = data.risk_score || '0';
            document.getElementById('editorRiskScore').className = getRiskBadgeClass(data.risk_score);
            document.getElementById('editorKeywords').textContent = data.keywords_matched || 'None';

            // Update character and word counts
            updateCounts();

            // Generate preview
            updatePreview();

            // Show the modal
            const modal = new bootstrap.Modal(document.getElementById('emailEditorModal'));
            modal.show();
        })
        .catch(error => {
            console.error('Error loading email:', error);
            alert(`Failed to load email: ${error.message}`);
        });
}

// Get risk badge class based on score
function getRiskBadgeClass(score) {
    score = parseInt(score) || 0;
    if (score >= 70) return 'badge bg-danger';
    if (score >= 40) return 'badge bg-warning text-dark';
    return 'badge bg-success';
}

// Update character and word counts
function updateCounts() {
    const body = document.getElementById('editorEmailBody').value;
    const charCount = body.length;
    const wordCount = body.trim() ? body.trim().split(/\s+/).length : 0;

    document.getElementById('charCount').textContent = charCount;
    document.getElementById('wordCount').textContent = wordCount;
}

// Update preview from plain text
function updatePreview() {
    const subject = document.getElementById('editorEmailSubject').value;
    const body = document.getElementById('editorEmailBody').value;
    const from = document.getElementById('editorEmailFrom').textContent;
    const to = document.getElementById('editorEmailTo').textContent;

    // Convert plain text to HTML with basic formatting
    let htmlBody = body
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/__(.*?)__/g, '<u>$1</u>');

    // Build preview HTML
    const previewHtml = `
        <div class="email-preview">
            <div class="mb-3 p-2 bg-light rounded">
                <div><strong>From:</strong> ${from}</div>
                <div><strong>To:</strong> ${to}</div>
                <div><strong>Subject:</strong> ${subject}</div>
            </div>
            <hr>
            <div class="email-body">
                <p>${htmlBody}</p>
            </div>
        </div>
    `;

    document.getElementById('emailPreview').innerHTML = previewHtml;
}

// Insert formatting around selected text
function insertFormatting(prefix, suffix) {
    const textarea = document.getElementById('editorEmailBody');
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = textarea.value;
    const selectedText = text.substring(start, end);

    const newText = text.substring(0, start) + prefix + selectedText + suffix + text.substring(end);
    textarea.value = newText;

    // Reset cursor position
    textarea.selectionStart = start + prefix.length;
    textarea.selectionEnd = end + prefix.length;
    textarea.focus();

    updateCounts();
    updatePreview();
}

// Insert template text
function insertTemplate(type) {
    const textarea = document.getElementById('editorEmailBody');
    const cursorPos = textarea.selectionStart;
    const text = textarea.value;

    let template = '';
    switch(type) {
        case 'greeting':
            template = 'Dear [Name],\n\nI hope this email finds you well.\n\n';
            break;
        case 'signature':
            template = '\n\nBest regards,\n[Your Name]\n[Your Title]\n[Your Company]';
            break;
    }

    const newText = text.substring(0, cursorPos) + template + text.substring(cursorPos);
    textarea.value = newText;
    textarea.focus();

    updateCounts();
    updatePreview();
}

// Save email as draft
function saveEmailDraft() {
    const emailId = document.getElementById('editorEmailId').value;
    const subject = document.getElementById('editorEmailSubject').value;
    const bodyText = document.getElementById('editorEmailBody').value;
    const bodyHtml = document.getElementById('editorEmailBodyHtml').value;
    const reviewNotes = document.getElementById('editorReviewNotes').value;

    if (!subject || !bodyText) {
        alert('Subject and body are required');
        return;
    }

    // Show loading state
    const btn = event.target;
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';

    fetch(`/email/${emailId}/save`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            subject: subject,
            body_text: bodyText,
            body_html: bodyHtml,
            review_notes: reviewNotes,
            action: 'save_draft'
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.error) {
            alert(data.error);
            btn.disabled = false;
            btn.innerHTML = originalText;
        } else {
            btn.innerHTML = '<i class="bi bi-check-circle"></i> Saved!';
            setTimeout(() => {
                btn.disabled = false;
                btn.innerHTML = originalText;
            }, 2000);
        }
    })
    .catch(error => {
        console.error('Error saving draft:', error);
        alert(`Failed to save: ${error.message}`);
        btn.disabled = false;
        btn.innerHTML = originalText;
    });
}

// Approve and send email
async function approveAndSendEmail() {
    const emailId = document.getElementById('editorEmailId').value;
    const subject = document.getElementById('editorEmailSubject').value;
    const bodyText = document.getElementById('editorEmailBody').value;
    const bodyHtml = document.getElementById('editorEmailBodyHtml').value;
    const reviewNotes = document.getElementById('editorReviewNotes').value;

    if (!subject || !bodyText) {
        if (window.showError) showError('Subject and body are required');
        else alert('Subject and body are required');
        return;
    }

    const confirmed = window.confirmToast
        ? await new Promise(resolve => confirmToast('Are you sure you want to approve and send this email?', () => resolve(true), () => resolve(false)))
        : confirm('Are you sure you want to approve and send this email?');
    if (!confirmed) {
        return;
    }

    // Show loading state
    const btn = event.target;
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Sending...';

    fetch(`/email/${emailId}/approve-send`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            subject: subject,
            body_text: bodyText,
            body_html: bodyHtml,
            review_notes: reviewNotes,
            action: 'approve_send'
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.error) {
            alert(data.error);
            btn.disabled = false;
            btn.innerHTML = originalText;
        } else {
            btn.innerHTML = '<i class="bi bi-check-circle"></i> Sent!';
            setTimeout(() => {
                // Close modal and reload page
                const modal = bootstrap.Modal.getInstance(document.getElementById('emailEditorModal'));
                modal.hide();
                location.reload();
            }, 1000);
        }
    })
    .catch(error => {
        console.error('Error sending email:', error);
        alert(`Failed to send: ${error.message}`);
        btn.disabled = false;
        btn.innerHTML = originalText;
    });
}

// Reject email from editor
async function rejectEmailFromEditor() {
    const emailId = document.getElementById('editorEmailId').value;
    const reviewNotes = document.getElementById('editorReviewNotes').value;

    const confirmed = window.confirmToast
        ? await new Promise(resolve => confirmToast('Are you sure you want to reject this email? It will not be sent.', () => resolve(true), () => resolve(false)))
        : confirm('Are you sure you want to reject this email? It will not be sent.');
    if (!confirmed) {
        return;
    }

    fetch(`/email/${emailId}/reject`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            review_notes: reviewNotes,
            action: 'reject'
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        if (data.error) {
            alert(data.error);
        } else {
            const modal = bootstrap.Modal.getInstance(document.getElementById('emailEditorModal'));
            modal.hide();
            location.reload();
        }
    })
    .catch(error => {
        console.error('Error rejecting email:', error);
        alert(`Failed to reject: ${error.message}`);
    });
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Update counts on typing
    const bodyTextarea = document.getElementById('editorEmailBody');
    if (bodyTextarea) {
        bodyTextarea.addEventListener('input', function() {
            updateCounts();
            updatePreview();
        });
    }

    // Update preview on subject change
    const subjectInput = document.getElementById('editorEmailSubject');
    if (subjectInput) {
        subjectInput.addEventListener('input', updatePreview);
    }

    // Tab switching
    document.getElementById('preview-tab')?.addEventListener('shown.bs.tab', updatePreview);
});