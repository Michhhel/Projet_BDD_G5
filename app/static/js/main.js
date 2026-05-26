// =============================================================================
// ENSEA — main.js : initialisation globale (DataTables, tooltips, spinner...)
// =============================================================================

$(function () {

  // ── DataTables : initialisation automatique sur toutes les tables .datatable ──
  $('.datatable').each(function () {
    if ($.fn.DataTable && !$.fn.DataTable.isDataTable(this)) {
      $(this).DataTable({
        language: {
          decimal:        ',',
          thousands:      ' ',
          emptyTable:     'Aucune donnée disponible.',
          info:           'Affichage de _START_ à _END_ sur _TOTAL_ lignes',
          infoEmpty:      '0 ligne sur 0',
          infoFiltered:   '(filtré sur _MAX_ lignes au total)',
          lengthMenu:     'Afficher _MENU_ lignes',
          loadingRecords: 'Chargement...',
          processing:     'Traitement...',
          search:         'Rechercher :',
          zeroRecords:    'Aucune correspondance trouvée.',
          paginate: {
            first:    'Première',
            last:     'Dernière',
            next:     'Suivant',
            previous: 'Précédent',
          },
        },
        pageLength: 25,
        responsive: true,
        order: [],   // pas de tri par défaut
      });
    }
  });

  // ── Bootstrap tooltips ──────────────────────────────────────────────────
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
    new bootstrap.Tooltip(el);
  });

  // ── Spinner sur soumission de formulaires ────────────────────────────────
  // Affiche le spinner pour les formulaires marqués enctype multipart
  // (imports Excel) et tout formulaire .form-with-spinner
  $('form[enctype="multipart/form-data"], .form-with-spinner').on('submit', function () {
    $('#globalSpinner').removeClass('d-none');
  });

  // ── Auto-dismiss des flash messages après 6 secondes ────────────────────
  setTimeout(function () {
    $('.alert.alert-success, .alert.alert-info').each(function () {
      const alert = bootstrap.Alert.getOrCreateInstance(this);
      alert.close();
    });
  }, 6000);

  // ── Confirmation native sur les formulaires .confirm-action ─────────────
  $('form.confirm-action').on('submit', function (e) {
    const msg = $(this).data('confirm-msg') || 'Confirmer cette action ?';
    if (!confirm(msg)) e.preventDefault();
  });

});


// =============================================================================
// Helpers globaux
// =============================================================================

/**
 * Charge le contenu d'un <select> en cascade via une API JSON.
 * @param {string} url           - URL de l'API
 * @param {jQuery} $select       - Le <select> à remplir
 * @param {string} value_field   - Champ servant de "value"
 * @param {string} label_field   - Champ servant de "texte affiché"
 * @param {string} placeholder   - Texte du premier <option>
 */
window.chargerCascade = function (url, $select, value_field, label_field, placeholder) {
  $select.html('<option value="0">' + placeholder + '</option>').prop('disabled', true);
  $.getJSON(url, function (data) {
    if (!data || !data.length) {
      $select.html('<option value="0">Aucune donnée disponible</option>');
      return;
    }
    data.forEach(function (item) {
      $select.append('<option value="' + item[value_field] + '">' + item[label_field] + '</option>');
    });
    $select.prop('disabled', false);
  });
};
