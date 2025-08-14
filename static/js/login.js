// Basic client-side UX for login form (demo only)
document.addEventListener('DOMContentLoaded', function() {
	const form = document.getElementById('login-form');
	if (!form) return;

	form.addEventListener('submit', async function(e) {
		e.preventDefault();
		const email = /** @type {HTMLInputElement} */(document.getElementById('email')).value.trim();
		const password = /** @type {HTMLInputElement} */(document.getElementById('password')).value;

		if (!email || !password) {
			window.AIInterviewer.notificationManager.show('Please enter email and password.', 'warning');
			return;
		}

		const submitBtn = form.querySelector('.auth-submit');
		if (submitBtn) {
			submitBtn.setAttribute('disabled', 'true');
			submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Signing in...';
		}

		try {
			// Demo only: pretend login succeeds and go home
			await new Promise(r => setTimeout(r, 800));
			window.AIInterviewer.notificationManager.show('Signed in successfully (demo).', 'success');
			window.location.href = '/';
		} catch (err) {
			window.AIInterviewer.notificationManager.show('Sign in failed. Please try again.', 'error');
		} finally {
			if (submitBtn) {
				submitBtn.removeAttribute('disabled');
				submitBtn.innerHTML = '<i class="fas fa-right-to-bracket"></i> Sign In';
			}
		}
	});
});


