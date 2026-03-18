<script lang="ts">
	import {
		Users,
		FolderSync,
		AlertTriangle,
		Loader2,
		Calendar,
		Crown
	} from 'lucide-svelte';
	import type {
		SyncTeam,
		StatItem
	} from '$lib/api-types';
	import StatsGrid from '$lib/components/StatsGrid.svelte';

	interface Props {
		team: SyncTeam;
		teamName: string;
		onleave: () => void;
		deleteConfirm: boolean;
		deleting: boolean;
		deleteError: string | null;
		ondeleteconfirm: (v: boolean) => void;
		ondeleteerror: (v: string | null) => void;
	}

	let {
		team,
		teamName,

		onleave,
		deleteConfirm,
		deleting,
		deleteError,
		ondeleteconfirm,
		ondeleteerror
	}: Props = $props();

	// Derived state
	let members = $derived(team.members ?? []);
	let projects = $derived(team.projects ?? []);
	let activeCount = $derived(members.filter((m) => m.status === 'active').length);
	let sharedProjects = $derived(projects.filter((p) => p.status === 'shared').length);

	// Format created_at date
	let createdDate = $derived.by(() => {
		if (!team.created_at) return null;
		try {
			return new Date(team.created_at).toLocaleDateString('en-US', {
				month: 'short',
				day: 'numeric',
				year: 'numeric'
			});
		} catch {
			return null;
		}
	});

	// Stats for StatsGrid
	let stats = $derived<StatItem[]>([
		{
			title: 'Members',
			value: `${activeCount}/${members.length}`,
			description: 'active',
			icon: Users,
			color: 'green'
		},
		{
			title: 'Projects',
			value: sharedProjects,
			description: `${projects.length} total`,
			icon: FolderSync,
			color: 'blue'
		}
	]);
</script>

<div class="space-y-8">
	<!-- Team Info Card -->
	<section class="rounded-lg border border-[var(--border)] bg-[var(--bg-subtle)] p-5">
		<div class="flex items-start justify-between">
			<div class="space-y-3">
				<div class="flex items-center gap-3">
					<h2 class="text-lg font-semibold text-[var(--text-primary)]">{team.name}</h2>
					<span class="px-2 py-0.5 text-[11px] font-medium rounded-full
						{team.status === 'active'
							? 'bg-[var(--success)]/10 text-[var(--success)] border border-[var(--success)]/20'
							: 'bg-[var(--error)]/10 text-[var(--error)] border border-[var(--error)]/20'}">
						{team.status}
					</span>
				</div>
				<div class="flex items-center gap-4 text-xs text-[var(--text-muted)]">
					<span class="flex items-center gap-1.5">
						<Crown size={12} class="text-[var(--warning)]" />
						Leader: <span class="font-medium text-[var(--text-secondary)]">{team.leader_member_tag}</span>
					</span>
					{#if createdDate}
						<span class="flex items-center gap-1.5">
							<Calendar size={12} />
							Created {createdDate}
						</span>
					{/if}
				</div>
			</div>
		</div>
	</section>

	<!-- Stats Row -->
	<section>
		<StatsGrid {stats} columns={2} />
	</section>

	<!-- Danger Zone (bottom, collapsible) -->
	<section class="mt-12">
		<details class="group" ontoggle={(e: Event) => { if (!(e.currentTarget as HTMLDetailsElement).open) { ondeleteconfirm(false); ondeleteerror(null); } }}>
			<summary class="flex items-center gap-2 cursor-pointer select-none text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors py-2">
				<span class="w-full border-t border-[var(--border)]/40"></span>
				<span class="shrink-0 flex items-center gap-1.5 uppercase tracking-wider font-medium">
					<AlertTriangle size={11} />
					Danger Zone
				</span>
				<span class="w-full border-t border-[var(--border)]/40"></span>
			</summary>
			<div class="pt-4">
				{#if deleteConfirm}
					<div class="space-y-2">
						<div class="flex items-center gap-3 p-4 rounded-lg border border-[var(--error)]/20 bg-[var(--error)]/5">
							<AlertTriangle size={16} class="text-[var(--error)] shrink-0" />
							<p class="text-sm text-[var(--text-primary)] flex-1">
								Leave team "{teamName}"? This will stop syncing with all members and clean up Syncthing folders.
							</p>
							<div class="flex items-center gap-2 shrink-0">
								<button
									onclick={onleave}
									disabled={deleting}
									class="px-3 py-1.5 text-xs font-medium rounded bg-[var(--error)] text-white hover:bg-[var(--error)]/80 transition-colors disabled:opacity-50"
								>
									{#if deleting}
										<Loader2 size={12} class="animate-spin" />
									{:else}
										Leave
									{/if}
								</button>
								<button
									onclick={() => { ondeleteconfirm(false); ondeleteerror(null); }}
									class="px-3 py-1.5 text-xs rounded text-[var(--text-muted)] hover:bg-[var(--bg-muted)] transition-colors"
								>
									Cancel
								</button>
							</div>
						</div>
						{#if deleteError}
							<p class="text-xs text-[var(--error)]" aria-live="polite">{deleteError}</p>
						{/if}
					</div>
				{:else}
					<button
						onclick={() => ondeleteconfirm(true)}
						class="px-4 py-2 text-sm font-medium rounded-[var(--radius-md)] border border-[var(--border)]
							text-[var(--text-muted)] hover:text-[var(--error)] hover:border-[var(--error)]/30 hover:bg-[var(--error)]/5 transition-colors"
					>
						Leave Team
					</button>
				{/if}
			</div>
		</details>
	</section>
</div>
