/* DSS Library Carousel — Vanilla JS */
/* Sacred constants: scroll 3 cards per click (3·6·9) */
(function() {
  document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.carousel-wrapper').forEach(function(wrapper) {
      var track = wrapper.querySelector('.carousel-track');
      var prev = wrapper.querySelector('.carousel-prev');
      var next = wrapper.querySelector('.carousel-next');
      var scrollAmount = 714; /* 3 × (220px card + 18px gap) */

      function updateButtons() {
        if (prev) prev.style.opacity = track.scrollLeft <= 0 ? '0.3' : '1';
        if (next) next.style.opacity = track.scrollLeft >= track.scrollWidth - track.clientWidth - 2 ? '0.3' : '1';
      }

      if (prev) prev.addEventListener('click', function() {
        track.scrollBy({ left: -scrollAmount, behavior: 'smooth' });
      });

      if (next) next.addEventListener('click', function() {
        track.scrollBy({ left: scrollAmount, behavior: 'smooth' });
      });

      track.addEventListener('scroll', updateButtons);
      updateButtons();
      window.addEventListener('resize', updateButtons);
    });
  });
})();
