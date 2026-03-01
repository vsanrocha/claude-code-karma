<script lang="ts">
	import { Handle, Position, type NodeProps } from '@xyflow/svelte';

	let { data }: NodeProps = $props();

	const modelColors: Record<string, { bg: string; text: string; border: string }> = {
		sonnet: { bg: 'rgba(139, 92, 246, 0.15)', text: '#a78bfa', border: '#8b5cf6' },
		opus: { bg: 'rgba(245, 158, 11, 0.15)', text: '#fbbf24', border: '#f59e0b' },
		haiku: { bg: 'rgba(16, 185, 129, 0.15)', text: '#34d399', border: '#10b981' }
	};

	let colors = $derived(modelColors[data.model as string] ?? modelColors.sonnet);
</script>

<Handle type="target" position={Position.Top} />

<div class="step-node">
	<div class="step-label">{data.label ?? data.id}</div>
	{#if data.model}
		<span
			class="model-badge"
			style="background: {colors.bg}; color: {colors.text}; border-color: {colors.border};"
		>
			{data.model}
		</span>
	{/if}
</div>

<Handle type="source" position={Position.Bottom} />

<style>
	.step-node {
		background: var(--bg-subtle);
		border: 1px solid var(--border);
		border-radius: 6px;
		padding: 10px 16px;
		min-width: 160px;
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 13px;
		color: var(--text-primary);
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
		transition: border-color 0.15s ease;
	}

	.step-node:hover {
		border-color: var(--accent);
	}

	.step-label {
		flex: 1;
		font-weight: 500;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.model-badge {
		font-size: 10px;
		padding: 2px 6px;
		border-radius: 4px;
		border: 1px solid;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		flex-shrink: 0;
	}
</style>
