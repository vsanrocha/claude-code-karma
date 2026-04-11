<script lang="ts">
	import type { TimelineEvent, TimelineEventType } from '$lib/api-types';

	interface Props {
		/** All raw events (unfiltered) — determines segment positions */
		events: TimelineEvent[];
		/** IDs of events that pass the current filter.
		 *  Empty Set = no active filter (all segments fully visible).
		 *  Non-empty Set = only these IDs are opaque; others get opacity: 0. */
		matchingEventIds: Set<string>;
		/** Whether any filter is currently active */
		hasActiveFilter: boolean;
	}

	let { events, matchingEventIds, hasActiveFilter }: Props = $props();

	// State for tooltip
	let hoveredEventId = $state<string | null>(null);
	let tooltipPos = $state({ x: 0, y: 0 });

	// CSS variable name per event_type
	const colorVar: Record<TimelineEventType, string> = {
		prompt: 'var(--event-prompt)',
		tool_call: 'var(--event-tool)',
		subagent_spawn: 'var(--event-subagent)',
		thinking: 'var(--event-thinking)',
		response: 'var(--event-response)',
		todo_update: 'var(--event-todo)',
		command_invocation: 'var(--event-command)',
		skill_invocation: 'var(--accent)',
		builtin_command: 'var(--event-builtin)'
	};

	// Display labels for event types
	const eventTypeLabel: Record<TimelineEventType, string> = {
		prompt: 'User Prompt',
		tool_call: 'Tool Call',
		subagent_spawn: 'Subagent',
		thinking: 'Thinking',
		response: 'Response',
		todo_update: 'Todo Update',
		command_invocation: 'Command',
		skill_invocation: 'Skill',
		builtin_command: 'Command'
	};

	function segmentColor(event: TimelineEvent): string {
		return colorVar[event.event_type] ?? 'var(--text-muted)';
	}

	function handleMouseEnter(event: TimelineEvent, e: MouseEvent) {
		hoveredEventId = event.id;
		const rect = (e.target as HTMLElement).getBoundingClientRect();
		tooltipPos = {
			x: rect.left + rect.width / 2,
			y: rect.top - 8
		};
	}

	function handleMouseLeave() {
		hoveredEventId = null;
	}
</script>

{#if events.length > 0}
	<div
		class="overview-container"
		role="img"
		aria-label="Timeline overview — {events.length} events"
	>
		<div class="overview-bar">
			{#each events as event (event.id)}
				<div
					class="segment"
					class:filtered={hasActiveFilter && !matchingEventIds.has(event.id)}
					role="button"
					tabindex="0"
					style="--segment-color: {segmentColor(event)};"
					onmouseenter={(e) => handleMouseEnter(event, e)}
					onmouseleave={handleMouseLeave}
				></div>
			{/each}
		</div>

		{#if hoveredEventId}
			{@const hoveredEvent = events.find((e) => e.id === hoveredEventId)}
			{#if hoveredEvent}
				<div
					class="tooltip"
					style="left: {tooltipPos.x}px; top: {tooltipPos.y}px; background-color: {segmentColor(hoveredEvent)};"
				>
					<div class="tooltip-label">
						{eventTypeLabel[hoveredEvent.event_type] || hoveredEvent.event_type}
					</div>
				</div>
			{/if}
		{/if}
	</div>
{/if}

<style>
	.overview-container {
		position: relative;
		margin-bottom: 1rem;
	}

	.overview-bar {
		display: flex;
		width: 100%;
		height: 50px;
		border-radius: 6px;
		border: 1px solid var(--border);
		overflow: hidden;
		background-color: var(--bg-subtle);
		gap: 1px;
	}

	.segment {
		flex: 1;
		min-width: 1px;
		transition: opacity 200ms ease;
		cursor: pointer;
		background-color: var(--segment-color);
		opacity: 0.6;
	}

	.segment.filtered {
		opacity: 0;
	}

	.segment:hover {
		opacity: 0.8;
	}

	.segment.filtered:hover {
		opacity: 0;
	}

	.tooltip {
		position: fixed;
		transform: translate(-50%, -100%);
		padding: 6px 12px;
		border-radius: 4px;
		font-size: 12px;
		font-weight: 500;
		white-space: nowrap;
		color: var(--bg-base);
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
		z-index: 50;
		pointer-events: none;
	}

	.tooltip-label {
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.tooltip::after {
		content: '';
		position: absolute;
		top: 100%;
		left: 50%;
		transform: translateX(-50%);
		width: 0;
		height: 0;
		border-left: 4px solid transparent;
		border-right: 4px solid transparent;
		border-top: 4px solid currentColor;
		opacity: 0.8;
	}
</style>
