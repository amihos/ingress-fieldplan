#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import matplotlib.pyplot as plt
import numpy as np
import os
import logging

from lib import maxfield
from matplotlib.patches import Polygon

logger = logging.getLogger('fieldplan')


def shrink(a):
    centroid = a.mean(1).reshape([2, 1])
    return centroid + 0.9 * (a-centroid)


def draw_edge(a, s, t, fig, marker, directional=False):
    eart = list()
    edge = np.array([a.nodes[s]['xy'], a.nodes[t]['xy']]).T
    eart += fig.plot(edge[0], edge[1], marker, lw=2)

    if directional:
        # Imitate an arrow to show which way direction is going
        x0 = edge[0][0]
        x1 = edge[0][1]
        y0 = edge[1][0]
        y1 = edge[1][1]

        eart += fig.plot([x1-0.05*(x1-x0), x1-0.4*(x1-x0)],
                         [y1-0.05*(y1-y0), y1-0.4*(y1-y0)], marker, lw=6)

    return eart


def make_json(outfile, faction):
    import json
    a = maxfield.active_graph
    tint = {
        'enl': '#51c34a',
        'res': '#4aa8c3',
    }
    js = []
    for p, q in a.edges():
        for tri in a.edges[p, q]['fields']:
            latlng = list()
            for v in tri:
                coords = a.nodes[v]['pll'].split(',')
                latlng.append(
                    {
                        'lat': float(coords[0]),
                        'lng': float(coords[1]),
                    }
                )
            js.append(
                {
                    'type': 'polygon',
                    'latLngs': latlng,
                    'color': tint[faction],
                }
            )
    with open(outfile, 'w') as jsout:
        json.dump(js, jsout)

    logger.info('Wrote json map dump into %s', outfile)


def make_png_steps(workplan, outdir, faction, plotdpi=96):
    logger.info('Generating step-by-step pngs of the workplan')
    if not os.path.isdir(outdir):
        os.mkdir(outdir)

    a = maxfield.active_graph
    ap = maxfield.portal_graph

    c_grn = (0.0, 1.0, 0.0, 0.3)
    c_blu = (0.0, 0.0, 1.0, 0.3)
    c_red = (1.0, 0.0, 0.0, 0.5)
    c_inv = (0.0, 0.0, 0.0, 0.0)

    portals = np.array([ap.nodes[i]['xy'] for i in ap.nodes()]).T

    fig = plt.figure(figsize=(11, 8), dpi=plotdpi)
    frames = list()
    ax = fig.add_subplot(1, 1, 1)
    ax.axis('off')

    ax.plot(portals[0], portals[1], 'ko')
    ax.set_title('Portals before capture', ha='center')

    filen = os.path.join(outdir, 'step_{0:03d}.png'.format(len(frames)))
    fig.savefig(filen)
    frames.append(filen)

    p = prev_p = prev_special = None
    seen_p = list()
    for p, q, f in workplan:
        if p != prev_p:
            torm = list()
            special = a.nodes[p]['special']
            if special is None:
                # Colour this nodes captured
                p_coords = np.array(a.nodes[p]['xy']).T
                if faction == 'res':
                    ax.plot(p_coords[0], p_coords[1], 'bo')
                else:
                    ax.plot(p_coords[0], p_coords[1], 'go')

            if prev_p is not None:
                # Show travel edge
                if special == '_w_blocker':
                    action = 'Destroy blocker'
                elif special in ('_w_start', '_w_end'):
                    action = 'Travel to waypoint'
                else:
                    if prev_special is None:
                        torm = draw_edge(a, prev_p, p, ax, 'm:', directional=True)
                    action = 'Capture'

                dist = maxfield.get_portal_distance(prev_p, p)
                if p not in seen_p:
                    if dist > 40:
                        ax.set_title('%s %s (%s m)' % (action, a.nodes[p]['name'], dist), ha='center')
                    else:
                        ax.set_title('%s %s' % (action, a.nodes[p]['name']), ha='center')
                else:
                    if dist > 40:
                        ax.set_title('Travel to %s (%s m)' % (a.nodes[p]['name'], dist), ha='center')
                    else:
                        ax.set_title('Move to %s' % a.nodes[p]['name'], ha='center')
            else:
                ax.set_title('Start at %s' % a.nodes[p]['name'], ha='center')

            filen = os.path.join(outdir, 'step_{0:03d}.png'.format(len(frames)))
            fig.savefig(filen)
            frames.append(filen)
            for art in torm:
                art.remove()

        prev_p = p
        prev_special = special
        if p not in seen_p:
            seen_p.append(p)

        if q is None:
            continue

        ax.set_title('Link to %s' % a.nodes[q]['name'], ha='center')

        # Draw the link edge
        torm = draw_edge(a, p, q, ax, 'k-', directional=True)

        fields = list()
        if f:
            # We'll display the new fields in red
            for tri in a.edges[p, q]['fields']:
                coords = np.array([a.nodes[v]['xy'] for v in tri])
                fields.append(Polygon(shrink(coords.T).T, facecolor=c_red,
                                      edgecolor=c_inv))

            for field in fields:
                torm.append(ax.add_patch(field))

        filen = os.path.join(outdir, 'step_{0:03d}.png'.format(len(frames)))
        fig.savefig(filen)
        frames.append(filen)

        # remove the newly added edges and triangles from the graph
        for art in torm:
            art.remove()
        # redraw the new edges and fields in the final colour
        if faction == 'res':
            draw_edge(a, p, q, ax, 'b-')
        else:
            draw_edge(a, p, q, ax, 'g-')

        if f:
            # reset fields to faction color
            for field in fields:
                if faction == 'res':
                    field.set_facecolor(c_blu)
                else:
                    field.set_facecolor(c_grn)
                ax.add_patch(field)

    # Save final frame with all completed fields
    ax.set_title('Finish at %s' % a.nodes[p]['name'], ha='center')
    filen = os.path.join(outdir, 'step_{0:03d}.png'.format(len(frames)))
    fig.savefig(filen)
    frames.append(filen)

    logger.info('Saved step-by-step pngs into %s', outdir)
