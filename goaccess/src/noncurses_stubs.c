#if !defined(HAVE_LIBNCURSES) && !defined(HAVE_LIBNCURSESW)

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/stat.h>
#include <pthread.h>
#include <unistd.h>

#include "commons.h"
#include "ui.h"
#include "color.h"
#include "goaccess.h"
#include "xmalloc.h"
#include "error.h"
#include "util.h"

static pthread_mutex_t spin_mutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_t spinner_thread;
static int spinner_running = 0;

static void *spinner_runner(void *ptr) {
  (void)ptr;
  while (spinner_running) {
    sleep(1);
  }
  return NULL;
}

/* CAE output definitions - mirrors ui.c outputting[] */
static const GOutput cae_outputting[] = {
  {CAE_EVENTS       , 1 , 0 , 0 , 0 , 0 , 1 , 0 , 1 , 1},
  {CAE_MODULE_DIST  , 1 , 0 , 1 , 0 , 0 , 1 , 0 , 0 , 1},
  {CAE_SEVERITY     , 1 , 0 , 0 , 1 , 1 , 1 , 1 , 0 , 1},
  {CAE_DURATION     , 1 , 0 , 0 , 0 , 0 , 1 , 1 , 1 , 1},
  {CAE_SESSION      , 1 , 1 , 0 , 0 , 0 , 1 , 0 , 0 , 1},
  {CAE_TIMELINE     , 1 , 0 , 1 , 0 , 0 , 1 , 0 , 1 , 1},
};

const GOutput *
output_lookup (GModule module) {
  int i, num_panels = ARRAY_SIZE (cae_outputting);
  for (i = 0; i < num_panels; i++) {
    if (cae_outputting[i].module == module)
      return &cae_outputting[i];
  }
  return NULL;
}

const char *
module_to_label (GModule module) {
  switch (module) {
  case CAE_EVENTS:       return "Events";
  case CAE_MODULE_DIST:  return "Module Distribution";
  case CAE_SEVERITY:     return "Severity";
  case CAE_DURATION:     return "Duration";
  case CAE_SESSION:      return "Session";
  case CAE_TIMELINE:     return "Timeline";
  }
  return "Unknown";
}

const char *
module_to_id (GModule module) {
  switch (module) {
  case CAE_EVENTS:       return "CAE_EVENTS";
  case CAE_MODULE_DIST:  return "CAE_MODULE_DIST";
  case CAE_SEVERITY:     return "CAE_SEVERITY";
  case CAE_DURATION:     return "CAE_DURATION";
  case CAE_SESSION:      return "CAE_SESSION";
  case CAE_TIMELINE:     return "CAE_TIMELINE";
  }
  return "CAE_UNKNOWN";
}

const char *
module_to_head (GModule module) {
  switch (module) {
  case CAE_EVENTS:       return "Events";
  case CAE_MODULE_DIST:  return "Module Distribution";
  case CAE_SEVERITY:     return "Severity";
  case CAE_DURATION:     return "Duration";
  case CAE_SESSION:      return "Session";
  case CAE_TIMELINE:     return "Timeline";
  }
  return "Unknown";
}

const char *
module_to_desc (GModule module) {
  return module_to_label (module);
}

void
generate_time (void) {
  if (conf.tz_name)
    set_tz ();
  timestamp = time (NULL);
  localtime_r (&timestamp, &now_tm);
}

int
get_start_end_parsing_dates (char **start, char **end, const char *f) {
  (void)f;
  *start = xstrdup ("N/A");
  *end = xstrdup ("N/A");
  return 0;
}

GSpinner *
new_gspinner (void) {
  return (GSpinner *)xcalloc (1, sizeof (GSpinner));
}

void
ui_spinner_create (GSpinner *spinner) {
  (void)spinner;
  spinner_running = 1;
  pthread_create (&spinner_thread, NULL, spinner_runner, NULL);
}

void
end_spinner (void) {
  spinner_running = 0;
  pthread_join (spinner_thread, NULL);
}

void
lock_spinner (void) {
  pthread_mutex_lock (&spin_mutex);
}

void
unlock_spinner (void) {
  pthread_mutex_unlock (&spin_mutex);
}

void
free_item_expanded (GScrollModule *smod) {
  if (smod->item_expanded) {
    free (smod->item_expanded);
    smod->item_expanded = NULL;
  }
}

void
init_item_expanded (GScrollModule *smod, int num_items) {
  smod->item_expanded = (uint8_t *)xcalloc (num_items, sizeof (uint8_t));
  smod->item_expanded_size = num_items;
}

void
reset_item_expanded (GScrollModule *smod) {
  if (smod->item_expanded)
    memset (smod->item_expanded, 0, (size_t)smod->item_expanded_size);
}

void
free_color_lists (void) {
}

#endif
