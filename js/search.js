/* Library Search — Digital Sovereign Society */
/* Client-side filtering across all library sections */

(function() {
  const input = document.getElementById('library-search');
  const countEl = document.getElementById('search-count');
  if (!input) return;

  // All searchable items: cards, carousel cards, and their parent sections
  const sections = document.querySelectorAll('section:not(.about-hero)');

  let debounceTimer;

  input.addEventListener('input', function() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function() {
      performSearch(input.value.trim().toLowerCase());
    }, 200);
  });

  function performSearch(query) {
    if (!query) {
      // Reset — show everything
      sections.forEach(function(section) {
        section.classList.remove('search-hidden');
        section.querySelectorAll('.card, .carousel-card, .book-card').forEach(function(el) {
          el.classList.remove('search-hidden');
          el.classList.remove('search-highlight');
        });
      });
      countEl.classList.remove('active');
      return;
    }

    let totalVisible = 0;

    sections.forEach(function(section) {
      const items = section.querySelectorAll('.card, .carousel-card, .book-card');
      let sectionHasMatch = false;

      // Also check section headings
      const sectionHeading = section.querySelector('h2');
      const sectionDesc = section.querySelector('h2 + p');
      const sectionText = (
        (sectionHeading ? sectionHeading.textContent : '') + ' ' +
        (sectionDesc ? sectionDesc.textContent : '')
      ).toLowerCase();

      if (sectionText.indexOf(query) !== -1 && items.length > 0) {
        // Section heading matches — show all items in it
        sectionHasMatch = true;
        items.forEach(function(item) {
          item.classList.remove('search-hidden');
        });
        totalVisible += items.length;
      } else {
        items.forEach(function(item) {
          var text = item.textContent.toLowerCase();
          if (text.indexOf(query) !== -1) {
            item.classList.remove('search-hidden');
            sectionHasMatch = true;
            totalVisible++;
          } else {
            item.classList.add('search-hidden');
          }
        });
      }

      if (sectionHasMatch || items.length === 0) {
        section.classList.remove('search-hidden');
      } else {
        section.classList.add('search-hidden');
      }
    });

    // Remove previous highlights
    document.querySelectorAll('.search-highlight').forEach(function(el) {
      el.classList.remove('search-highlight');
    });

    countEl.textContent = totalVisible + ' result' + (totalVisible !== 1 ? 's' : '') + ' found';
    countEl.classList.add('active');

    // Scroll to and highlight first visible result
    if (totalVisible > 0) {
      var firstMatch = document.querySelector('section:not(.search-hidden) .card:not(.search-hidden), section:not(.search-hidden) .carousel-card:not(.search-hidden), section:not(.search-hidden) .book-card:not(.search-hidden)');
      if (firstMatch) {
        firstMatch.classList.add('search-highlight');
        firstMatch.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }
})();
