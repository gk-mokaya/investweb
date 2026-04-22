(function () {
  function getCookie(name) {
    var value = '; ' + document.cookie;
    var parts = value.split('; ' + name + '=');
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
  }

  function openModal(modal) {
    if (!modal) return;
    modal.classList.add('is-open');
    document.body.classList.add('modal-open');
  }

  function closeModal(modal) {
    if (!modal) return;
    modal.classList.remove('is-open');
    if (!document.querySelector('.modal.is-open')) {
      document.body.classList.remove('modal-open');
    }
  }

  document.querySelectorAll('.modal[data-open="true"]').forEach(function (modal) {
    openModal(modal);
  });

  document.addEventListener('click', function (event) {
    var openTrigger = event.target.closest('[data-modal-open]');
    if (openTrigger) {
      var target = openTrigger.getAttribute('data-modal-open');
      var modal = document.querySelector(target);
      openModal(modal);
      var planId = openTrigger.getAttribute('data-plan-id');
      if (planId) {
        var planSelect = document.getElementById('id_plan');
        if (planSelect) {
          planSelect.value = planId;
          planSelect.dispatchEvent(new Event('change', { bubbles: true }));
        }
      }
    }

    if (event.target.matches('.modal-backdrop') || event.target.closest('[data-modal-close]')) {
      var modalEl = event.target.closest('.modal') || event.target.parentElement?.closest('.modal');
      closeModal(modalEl);
    }

    var toggle = event.target.closest('[data-sidebar-toggle]');
    if (toggle) {
      var sidebar = document.querySelector('.sidebar');
      if (sidebar) {
        sidebar.classList.toggle('open');
      }
    }

    var alertClose = event.target.closest('[data-alert-close]');
    if (alertClose) {
      var alertEl = alertClose.closest('.alert');
      if (alertEl) alertEl.remove();
    }

    var toastClose = event.target.closest('[data-alert-close]');
    if (toastClose) {
      var toastEl = toastClose.closest('.toast');
      if (toastEl) toastEl.remove();
    }

    var notifToggle = event.target.closest('[data-notif-toggle]');
    if (notifToggle) {
      var notifWrap = notifToggle.closest('[data-notif-wrap]');
      if (notifWrap) {
        notifWrap.classList.toggle('is-open');
      }
      return;
    }

    if (!event.target.closest('[data-notif-wrap]')) {
      document.querySelectorAll('[data-notif-wrap].is-open').forEach(function (el) {
        el.classList.remove('is-open');
      });
    }
  });

  document.querySelectorAll('.toast').forEach(function (toast) {
    setTimeout(function () {
      if (toast && toast.parentElement) {
        toast.remove();
      }
    }, 5000);
  });

  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (!form || !form.method || form.method.toLowerCase() !== 'post') return;
    var submitter = event.submitter || form.querySelector('button[type=\"submit\"], input[type=\"submit\"]');
    if (!submitter) return;
    var confirmMessage = submitter.getAttribute('data-confirm') || form.getAttribute('data-confirm');
    if (confirmMessage && form.dataset.confirmed !== 'true') {
      event.preventDefault();
      openConfirmDialog(confirmMessage, form, submitter);
      return;
    }
    if (form.dataset.confirmed === 'true') {
      delete form.dataset.confirmed;
    }
    submitter.classList.add('is-loading');
    submitter.setAttribute('disabled', 'disabled');
  });

  document.querySelectorAll('[data-tabs]').forEach(function (tabs) {
    var container = tabs.closest('.section-card') || document;
    var buttons = tabs.querySelectorAll('.tab');
    var panels = container.querySelectorAll('[data-tab-panel]');
    function activateTab(target) {
      buttons.forEach(function (btn) {
        btn.classList.toggle('active', btn.getAttribute('data-tab') === target);
      });
      panels.forEach(function (panel) {
        panel.classList.toggle('active', panel.getAttribute('data-tab-panel') === target);
      });
    }
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        activateTab(btn.getAttribute('data-tab'));
      });
    });
  });

  var confirmBackdrop = document.getElementById('confirmBackdrop');
  var confirmDialog = document.getElementById('confirmDialog');
  var confirmTitle = document.getElementById('confirmTitle');
  var confirmMessageEl = document.getElementById('confirmMessage');
  var confirmCancel = document.querySelector('[data-confirm-cancel]');
  var confirmAccept = document.querySelector('[data-confirm-accept]');
  var confirmIconUse = confirmDialog ? confirmDialog.querySelector('.sweet-alert-icon use') : null;
  var confirmProgress = confirmDialog ? confirmDialog.querySelector('[data-confirm-progress]') : null;
  var confirmProgressBar = confirmDialog ? confirmDialog.querySelector('[data-confirm-progress-bar]') : null;
  var pendingForm = null;
  var pendingSubmitter = null;
  var confirmTimer = null;
  var confirmProgressValue = 0;

  function resolveConfirmStyle(message, form, submitter) {
    var explicit = submitter ? submitter.getAttribute('data-confirm-style') : null;
    if (explicit) return explicit;
    var action = (form && form.getAttribute('action')) ? form.getAttribute('action') : '';
    var lower = action.toLowerCase();
    if (lower.indexOf('reject') !== -1 || lower.indexOf('delete') !== -1) return 'danger';
    if (lower.indexOf('approve') !== -1 || lower.indexOf('paid') !== -1 || lower.indexOf('completed') !== -1) return 'success';
    if (lower.indexOf('verify') !== -1) return 'warning';
    return 'warning';
  }

  function applyConfirmStyle(style) {
    if (!confirmDialog) return;
    confirmDialog.classList.remove('success', 'warning', 'danger');
    confirmAccept.classList.remove('success', 'danger');
    if (style === 'success') {
      confirmDialog.classList.add('success');
      confirmAccept.classList.add('success');
      if (confirmIconUse) confirmIconUse.setAttribute('href', '#icon-check');
      return;
    }
    if (style === 'danger') {
      confirmDialog.classList.add('danger');
      confirmAccept.classList.add('danger');
      if (confirmIconUse) confirmIconUse.setAttribute('href', '#icon-x');
      return;
    }
    confirmDialog.classList.add('warning');
    if (confirmIconUse) confirmIconUse.setAttribute('href', '#icon-alert');
  }

  function openConfirmDialog(message, form, submitter) {
    if (!confirmBackdrop) return;
    pendingForm = form;
    pendingSubmitter = submitter;
    if (pendingSubmitter) {
      pendingSubmitter.setAttribute('disabled', 'disabled');
      pendingSubmitter.dataset.confirmDisabled = 'true';
    }
    var style = resolveConfirmStyle(message, form, submitter);
    applyConfirmStyle(style);
    confirmTitle.textContent = 'Please Confirm';
    confirmMessageEl.textContent = message;
    if (confirmProgress) {
      confirmProgress.style.display = 'none';
    }
    if (confirmProgressBar) {
      confirmProgressBar.style.width = '0%';
    }
    if (confirmTimer) {
      clearInterval(confirmTimer);
      confirmTimer = null;
    }
    confirmProgressValue = 0;
    confirmBackdrop.classList.add('is-open');
    confirmBackdrop.setAttribute('aria-hidden', 'false');
  }

  function closeConfirmDialog() {
    if (!confirmBackdrop) return;
    confirmBackdrop.classList.remove('is-open');
    confirmBackdrop.setAttribute('aria-hidden', 'true');
    pendingForm = null;
    pendingSubmitter = null;
    if (confirmProgress) {
      confirmProgress.style.display = 'none';
    }
    if (confirmProgressBar) {
      confirmProgressBar.style.width = '0%';
    }
    if (confirmTimer) {
      clearInterval(confirmTimer);
      confirmTimer = null;
    }
    confirmProgressValue = 0;
    if (confirmAccept) {
      confirmAccept.classList.remove('is-loading');
      confirmAccept.removeAttribute('disabled');
    }
    if (confirmCancel) {
      confirmCancel.removeAttribute('disabled');
    }
    if (pendingSubmitter && pendingSubmitter.dataset.confirmDisabled === 'true') {
      pendingSubmitter.removeAttribute('disabled');
      delete pendingSubmitter.dataset.confirmDisabled;
    }
  }

  if (confirmBackdrop) {
    confirmBackdrop.addEventListener('click', function (event) {
      if (event.target === confirmBackdrop) {
        closeConfirmDialog();
      }
    });
  }

  if (confirmCancel) {
    confirmCancel.addEventListener('click', function () {
      closeConfirmDialog();
    });
  }

  if (confirmAccept) {
    confirmAccept.addEventListener('click', function () {
      if (pendingForm) {
        pendingForm.dataset.confirmed = 'true';
        if (pendingSubmitter && pendingSubmitter.dataset.confirmDisabled === 'true') {
          pendingSubmitter.removeAttribute('disabled');
          delete pendingSubmitter.dataset.confirmDisabled;
        }
        if (confirmProgress) {
          confirmProgress.style.display = 'block';
        }
        if (confirmAccept) {
          confirmAccept.classList.add('is-loading');
          confirmAccept.setAttribute('disabled', 'disabled');
        }
        if (confirmCancel) {
          confirmCancel.setAttribute('disabled', 'disabled');
        }
        if (confirmTimer) {
          clearInterval(confirmTimer);
        }
        confirmTimer = setInterval(function () {
          confirmProgressValue = Math.min(confirmProgressValue + Math.random() * 12 + 4, 90);
          if (confirmProgressBar) {
            confirmProgressBar.style.width = confirmProgressValue + '%';
          }
        }, 200);
        setTimeout(function () {
          if (confirmProgressBar) {
            confirmProgressBar.style.width = '100%';
          }
        }, 1200);
        setTimeout(function () {
          closeConfirmDialog();
        }, 1400);
        if (pendingForm.requestSubmit) {
          pendingForm.requestSubmit(pendingSubmitter || undefined);
        } else {
          pendingForm.submit();
        }
      } else {
        closeConfirmDialog();
      }
    });
  }

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && confirmBackdrop && confirmBackdrop.classList.contains('is-open')) {
      closeConfirmDialog();
    }
  });

  function renderFilePreview(input) {
    var preview = document.querySelector('[data-preview-id=\"' + input.id + '\"]');
    if (!preview) return;
    if (!input.files || !input.files[0]) return;
    var file = input.files[0];
    var name = file.name || '';
    var isImage = file.type && file.type.indexOf('image/') === 0;
    var isPdf = file.type === 'application/pdf' || name.toLowerCase().endsWith('.pdf');
    preview.innerHTML = '';

    if (isImage) {
      var img = document.createElement('img');
      img.src = URL.createObjectURL(file);
      img.onload = function () { URL.revokeObjectURL(img.src); };
      preview.appendChild(img);
    } else if (isPdf) {
      var iconWrap = document.createElement('div');
      iconWrap.className = 'file-preview-icon';
      iconWrap.innerHTML = '<svg class=\"icon lg\"><use href=\"#icon-clipboard\"></use></svg>';
      preview.appendChild(iconWrap);
    } else {
      var empty = document.createElement('div');
      empty.className = 'file-preview-empty';
      empty.textContent = 'Unsupported file type';
      preview.appendChild(empty);
    }

    var label = document.createElement('div');
    label.className = 'file-preview-name';
    label.textContent = name;
    preview.appendChild(label);
  }

  document.querySelectorAll('input.file-input').forEach(function (input) {
    input.addEventListener('change', function () {
      renderFilePreview(input);
    });
  });

  document.querySelectorAll('select[data-wallet-balances]').forEach(function (select) {
    var balances = {};
    try {
      balances = JSON.parse(select.getAttribute('data-wallet-balances') || '{}');
    } catch (err) {
      balances = {};
    }
    var targetId = select.getAttribute('data-balance-target');
    var autoTargetId = select.getAttribute('data-autofill-target');
    var targetInput = targetId ? document.getElementById(targetId) : null;
    var autoInput = autoTargetId ? document.getElementById(autoTargetId) : null;
    if (autoInput) {
      autoInput.addEventListener('input', function () {
        autoInput.dataset.autoFilled = 'false';
      });
    }

    function updateBalance() {
      var value = select.value;
      var balance = balances[value] || '0';
      if (targetInput) {
        if (targetInput.tagName === 'INPUT' || targetInput.tagName === 'TEXTAREA' || targetInput.tagName === 'SELECT') {
          targetInput.value = balance;
        } else {
          targetInput.textContent = balance;
        }
      }
      if (autoInput) {
        if (!autoInput.value || autoInput.dataset.autoFilled !== 'false') {
          autoInput.value = balance;
          autoInput.dataset.autoFilled = 'true';
        }
      }
    }

    select.addEventListener('change', updateBalance);
    updateBalance();
  });

  function copyTextToClipboard(text) {
    if (!text) return Promise.reject(new Error('No text to copy'));
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      try {
        var textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.setAttribute('readonly', '');
        textarea.style.position = 'absolute';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        var ok = document.execCommand('copy');
        document.body.removeChild(textarea);
        if (ok) resolve();
        else reject(new Error('Copy failed'));
      } catch (err) {
        reject(err);
      }
    });
  }

  document.addEventListener('click', function (event) {
    var trigger = event.target.closest('[data-copy-text],[data-copy-target]');
    if (!trigger) return;
    event.preventDefault();
    var text = trigger.getAttribute('data-copy-text');
    if (!text) {
      var selector = trigger.getAttribute('data-copy-target');
      var target = selector ? document.querySelector(selector) : null;
      text = target ? (target.value || target.textContent || '').trim() : '';
    }
    copyTextToClipboard(text)
      .then(function () {
        var original = trigger.dataset.copyOriginal || trigger.textContent;
        if (!trigger.dataset.copyOriginal) {
          trigger.dataset.copyOriginal = original;
        }
        trigger.textContent = 'Copied';
        setTimeout(function () {
          if (trigger.dataset.copyOriginal) {
            trigger.textContent = trigger.dataset.copyOriginal;
          }
        }, 1500);
      })
      .catch(function () {
        var original = trigger.dataset.copyOriginal || trigger.textContent;
        if (!trigger.dataset.copyOriginal) {
          trigger.dataset.copyOriginal = original;
        }
        trigger.textContent = 'Copy failed';
        setTimeout(function () {
          if (trigger.dataset.copyOriginal) {
            trigger.textContent = trigger.dataset.copyOriginal;
          }
        }, 1500);
      });
  });

  function updateNotificationBadge(count) {
    document.querySelectorAll('[data-notif-badge]').forEach(function (badge) {
      var total = Number(count) || 0;
      badge.textContent = String(total);
      badge.style.display = total > 0 ? 'inline-flex' : 'none';
    });
  }

  function ensureNotificationEmptyState(list) {
    if (!list) return;
    var items = list.querySelectorAll('[data-notif-item]');
    var empty = list.querySelector('[data-notif-empty]');
    if (items.length === 0) {
      if (!empty) {
        var node = document.createElement('div');
        node.className = 'notif-empty';
        node.setAttribute('data-notif-empty', '');
        node.textContent = 'No new notifications.';
        list.appendChild(node);
      }
    } else if (empty) {
      empty.remove();
    }
  }

  function postNotificationAction(url, payload) {
    var body = new URLSearchParams(payload || {}).toString();
    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-CSRFToken': getCookie('csrftoken'),
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: body
    }).then(function (res) {
      if (!res.ok) throw new Error('Request failed');
      return res.json();
    });
  }

  document.querySelectorAll('[data-notif-list]').forEach(function (list) {
    ensureNotificationEmptyState(list);
  });

  document.addEventListener('click', function (event) {
    var item = event.target.closest('[data-notif-item]');
    if (item) {
      var id = item.getAttribute('data-id');
      if (!id) return;
      postNotificationAction('/accounts/notifications/read/', { notification_id: id })
        .then(function (data) {
          item.remove();
          var list = document.querySelector('[data-notif-list]');
          ensureNotificationEmptyState(list);
          if (!document.querySelector('[data-notif-item]')) {
            var clearBtn = document.querySelector('[data-notif-clear-all]');
            if (clearBtn) clearBtn.setAttribute('disabled', 'disabled');
          }
          if (data && Object.prototype.hasOwnProperty.call(data, 'unread')) {
            updateNotificationBadge(data.unread);
          }
        })
        .catch(function () {});
      return;
    }

    var clearAll = event.target.closest('[data-notif-clear-all]');
    if (clearAll) {
      postNotificationAction('/accounts/notifications/read-all/', {})
        .then(function () {
          document.querySelectorAll('[data-notif-item]').forEach(function (node) {
            node.remove();
          });
          document.querySelectorAll('[data-notif-list]').forEach(function (list) {
            ensureNotificationEmptyState(list);
          });
          updateNotificationBadge(0);
          clearAll.setAttribute('disabled', 'disabled');
        })
        .catch(function () {});
    }
  });

  function toggleMethodFields(select) {
    if (!select) return;
    var form = select.closest('form') || document;
    var method = select.value || '';
    form.querySelectorAll('[data-method-only]').forEach(function (field) {
      var requiredMethod = field.getAttribute('data-method-only');
      var group = field.closest('.form-group') || field;
      if (!group) return;
      if (method && method === requiredMethod) {
        group.style.display = '';
      } else {
        group.style.display = 'none';
      }
    });
    form.querySelectorAll('[data-method-required]').forEach(function (field) {
      var requiredMethod = field.getAttribute('data-method-required');
      if (method && method === requiredMethod) {
        field.setAttribute('required', 'required');
      } else {
        field.removeAttribute('required');
      }
    });
  }

  function parseNumber(value) {
    var num = parseFloat(value);
    return Number.isFinite(num) ? num : 0;
  }

  function formatMoney(value, currency) {
    var amount = Number.isFinite(value) ? value : 0;
    return amount.toFixed(2) + ' ' + currency;
  }

  function formatDate(value) {
    if (!(value instanceof Date) || Number.isNaN(value.getTime())) return '-';
    return new Intl.DateTimeFormat('en-US', { month: 'short', day: '2-digit', year: 'numeric' }).format(value);
  }

  function updateInvestmentForm(form) {
    if (!form) return;
    var planSelect = form.querySelector('[name=\"plan\"]');
    var walletSelect = form.querySelector('[name=\"wallet\"]');
    var amountInput = form.querySelector('[name=\"amount\"]');
    var currency = form.getAttribute('data-currency') || 'USD';
    var planMeta = {};
    if (planSelect) {
      try {
        planMeta = JSON.parse(planSelect.getAttribute('data-plan-meta') || '{}');
      } catch (err) {
        planMeta = {};
      }
    }

    var plan = planSelect && planSelect.value ? planMeta[planSelect.value] : null;
    var amount = amountInput ? parseNumber(amountInput.value) : 0;

    var amountHelp = form.querySelector('[data-plan-amount-help]');
    if (amountHelp) {
      if (plan) {
        var minText = plan.min_amount ? plan.min_amount + ' ' + currency : '-';
        var maxText = plan.max_amount ? plan.max_amount + ' ' + currency : 'No limit';
        var rangeText = 'Min ' + minText + ' · Max ' + maxText;
        var minValue = parseNumber(plan.min_amount);
        var maxValue = parseNumber(plan.max_amount);
        if (amount && minValue && amount < minValue) {
          amountHelp.textContent = rangeText + ' · Below minimum';
        } else if (amount && maxValue && amount > maxValue) {
          amountHelp.textContent = rangeText + ' · Above maximum';
        } else {
          amountHelp.textContent = rangeText;
        }
      } else {
        amountHelp.textContent = 'Select a plan to see min/max.';
      }
    }

    if (amountInput) {
      if (plan && plan.min_amount) {
        amountInput.setAttribute('min', plan.min_amount);
      }
      if (plan && plan.max_amount) {
        amountInput.setAttribute('max', plan.max_amount);
      } else {
        amountInput.removeAttribute('max');
      }
    }

    var setText = function (selector, text) {
      var el = form.querySelector(selector);
      if (el) el.textContent = text;
    };

    if (plan) {
      var dailyRoi = parseNumber(plan.daily_roi);
      var duration = Math.max(0, Math.floor(parseNumber(plan.duration_days)));
      var dailyProfit = amount ? (amount * dailyRoi) / 100 : 0;
      var grossProfit = amount ? dailyProfit * duration : 0;
      var totalPayout = amount ? amount + grossProfit : 0;
      setText('[data-overview-name]', plan.name || 'Selected plan');
      setText('[data-overview-daily]', amount ? formatMoney(dailyProfit, currency) : '-');
      setText('[data-overview-gross]', amount ? formatMoney(grossProfit, currency) : '-');
      setText('[data-overview-payout]', amount ? formatMoney(totalPayout, currency) : '-');
      setText('[data-overview-duration]', (plan.duration_days || '-') + ' days');
      setText('[data-overview-minmax]', (plan.min_amount || '-') + ' ' + currency + ' / ' + (plan.max_amount ? plan.max_amount + ' ' + currency : 'No limit'));
      setText('[data-overview-roi]', (plan.daily_roi || '0') + '%');
      setText('[data-overview-frequency]', plan.payout_frequency || '-');
      setText('[data-overview-liquidity]', plan.liquidity_terms || '-');
      setText('[data-overview-lock]', plan.lock_period_days ? plan.lock_period_days + ' days' : 'None');
      setText('[data-overview-risk]', plan.risk_level || '-');
      setText('[data-overview-fees]', (plan.management_fee_pct || '0') + '% mgmt / ' + (plan.early_withdrawal_fee_pct || '0') + '% early');
      setText('[data-overview-protection]', plan.capital_protection ? 'Yes' : 'No');
    } else {
      setText('[data-overview-name]', 'Select a plan to preview returns.');
      setText('[data-overview-daily]', '-');
      setText('[data-overview-gross]', '-');
      setText('[data-overview-payout]', '-');
      setText('[data-overview-duration]', '-');
      setText('[data-overview-minmax]', '-');
      setText('[data-overview-roi]', '-');
      setText('[data-overview-frequency]', '-');
      setText('[data-overview-liquidity]', '-');
      setText('[data-overview-lock]', '-');
      setText('[data-overview-risk]', '-');
      setText('[data-overview-fees]', '-');
      setText('[data-overview-protection]', '-');
    }

    var balanceHelp = form.querySelector('[data-wallet-balance-help]');
    var balanceStatus = form.querySelector('[data-wallet-balance-status]');
    var walletName = form.querySelector('[data-wallet-selected-name]');
    if (walletSelect && balanceHelp) {
      var balances = {};
      try {
        balances = JSON.parse(walletSelect.getAttribute('data-wallet-balances') || '{}');
      } catch (err) {
        balances = {};
      }
      var balanceValue = walletSelect.value ? parseNumber(balances[walletSelect.value]) : 0;
      var selectedOption = walletSelect.options[walletSelect.selectedIndex];
      var selectedWalletText = selectedOption ? selectedOption.textContent.trim() : '';
      if (!walletSelect.value) {
        if (walletName) {
          walletName.textContent = 'Choose a wallet';
        }
        balanceHelp.textContent = 'Select a wallet to see balance.';
        if (balanceStatus) {
          balanceStatus.style.display = 'none';
          balanceStatus.classList.remove('success', 'danger', 'warning', 'info');
        }
      } else {
        if (walletName) {
          walletName.textContent = selectedWalletText || 'Selected wallet';
        }
        balanceHelp.textContent = formatMoney(balanceValue, currency);
        if (balanceStatus) {
          balanceStatus.style.display = 'inline-flex';
          balanceStatus.classList.remove('success', 'danger', 'warning', 'info');
          if (amount && amount > balanceValue) {
            balanceStatus.classList.add('danger');
            balanceStatus.textContent = 'Insufficient';
          } else if (amount) {
            balanceStatus.classList.add('success');
            balanceStatus.textContent = 'Enough';
          } else {
            balanceStatus.classList.add('info');
            balanceStatus.textContent = 'Ready';
          }
        }
      }
    }
  }

  document.querySelectorAll('form[data-investment-form]').forEach(function (form) {
    var planSelect = form.querySelector('[name=\"plan\"]');
    var walletSelect = form.querySelector('[name=\"wallet\"]');
    var amountInput = form.querySelector('[name=\"amount\"]');
    var riskAck = form.querySelector('[name=\"risk_acknowledged\"]');
    var submitBtn = form.querySelector('button[type=\"submit\"], input[type=\"submit\"]');
    if (planSelect) {
      planSelect.addEventListener('change', function () {
        updateInvestmentForm(form);
      });
    }
    if (walletSelect) {
      walletSelect.addEventListener('change', function () {
        updateInvestmentForm(form);
      });
    }
    if (amountInput) {
      amountInput.addEventListener('input', function () {
        updateInvestmentForm(form);
      });
    }
    if (riskAck) {
      riskAck.setAttribute('required', 'required');
      var syncSubmit = function () {
        if (!submitBtn) return;
        submitBtn.disabled = !riskAck.checked;
      };
      riskAck.addEventListener('change', syncSubmit);
      syncSubmit();
    }
    updateInvestmentForm(form);
  });

  document.querySelectorAll('[name$=\"method\"]').forEach(function (input) {
    if (input.tagName === 'SELECT') {
      input.addEventListener('change', function () {
        toggleMethodFields(input);
      });
    }
    toggleMethodFields(input);
  });

  function formatAddressInGroups(raw, size) {
    var compact = String(raw || '').replace(/\s+/g, '');
    var groupSize = Number.isFinite(size) && size > 0 ? size : 4;
    var parts = [];
    for (var i = 0; i < compact.length; i += groupSize) {
      parts.push(compact.slice(i, i + groupSize));
    }
    return parts.join(' ');
  }

  document.querySelectorAll('[data-format-address=\"true\"]').forEach(function (el) {
    var raw = (el.textContent || '').trim();
    if (!raw) return;
    var groupSize = parseInt(el.getAttribute('data-group-size') || '4', 10);
    el.textContent = formatAddressInGroups(raw, groupSize);
  });

  function renderScheduleTables() {
    document.querySelectorAll('[data-schedule-table]').forEach(function (table) {
      var tbody = table.querySelector('tbody');
      if (!tbody) return;
      var startStr = table.getAttribute('data-start');
      var endStr = table.getAttribute('data-end');
      if (!startStr || !endStr) return;
      var startDate = new Date(startStr + 'T00:00:00');
      var endDate = new Date(endStr + 'T00:00:00');
      if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) return;

      var amount = parseNumber(table.getAttribute('data-amount'));
      var roi = parseNumber(table.getAttribute('data-roi'));
      var feePct = parseNumber(table.getAttribute('data-fee'));
      var currency = table.getAttribute('data-currency') || 'USD';
      var isCompleted = table.getAttribute('data-completed') === 'true';
      var earnedRaw = table.getAttribute('data-earned') || '[]';
      var earnedMap = {};
      try {
        var earnedList = JSON.parse(earnedRaw);
        earnedList.forEach(function (item) {
          if (item && item.date) {
            earnedMap[item.date] = parseNumber(item.amount);
          }
        });
      } catch (err) {
        earnedMap = {};
      }

      var dailyProfit = amount ? (amount * roi) / 100 : 0;
      var feeAmount = dailyProfit ? dailyProfit * (feePct / 100) : 0;
      var netProfit = dailyProfit - feeAmount;

      var today = new Date();
      today.setHours(0, 0, 0, 0);

      var rows = [];
      var cumulative = 0;
      var iter = 0;
      var cursor = new Date(startDate);
      while (cursor <= endDate && iter < 2000) {
        var cursorKey = cursor.toISOString().slice(0, 10);
        var hasEarned = Object.prototype.hasOwnProperty.call(earnedMap, cursorKey);
        var dayProfit = hasEarned ? earnedMap[cursorKey] : netProfit;
        cumulative += dayProfit;
        var status = hasEarned ? 'Earned' : 'Pending';
        var isPending = !hasEarned;
        if (!hasEarned && cursor <= today) {
          status = 'Pending';
        }
        if (hasEarned && isCompleted && cursor.getTime() === endDate.getTime()) {
          status = 'Completed';
        }
        var progressWidth = isPending ? 0 : 100;
        rows.push(
          '<tr class=\"' + (isPending ? 'is-pending' : 'is-earned') + '\">' +
            '<td data-label=\"Date\">' + formatDate(cursor) + '</td>' +
            '<td data-label=\"Daily Profit\">' + formatMoney(dayProfit, currency) + '</td>' +
            '<td data-label=\"Cumulative Profit\">' + formatMoney(cumulative, currency) + '</td>' +
            '<td data-label=\"Status\">' +
              '<div class=\"schedule-status\">' + status + '</div>' +
              '<div class=\"schedule-progress\"><span style=\"width: ' + progressWidth + '%\"></span></div>' +
            '</td>' +
          '</tr>'
        );
        cursor.setDate(cursor.getDate() + 1);
        iter += 1;
      }

      if (!rows.length) {
        rows.push('<tr><td colspan=\"4\"><div class=\"empty-state\">No schedule data available.</div></td></tr>');
      }

      tbody.innerHTML = rows.join('');
    });
  }

  renderScheduleTables();
})();
